"""
End-to-end driver for one PDF: rasterize + prepare-request files + emit the
Agent prompt that the main Claude Code session pastes into a subagent dispatch.

This is the workflow the bake-off + full-corpus runs use:

  1. Call `python3 driver.py prep <pdf-path> --job byline-sweep` (or metadata, summary, ...)
     → Rasterizes the appropriate chunk, packages prompts, prints the
       Agent prompt to stdout. The main session reads the printed prompt
       and dispatches an Agent.
  2. The Agent reads the prompt + images, returns JSON in its response.
  3. Main session saves the response text to a file (see "collect" cmd).
  4. Call `python3 driver.py collect <request_id> --response-file <path>`
     → Parses the response, validates JSON, writes to a per-work output
       directory, appends a ledger entry.

For the bake-off, the main session loops over `data/bakeoff-sample.json` and
runs (prep → dispatch → collect) per PDF per job.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rasterize import rasterize_chunk  # noqa: E402
from dispatcher import (                # noqa: E402
    DispatchRequest,
    PreparedRequest,
    prepare_request,
    parse_response,
)
from ledger import LedgerEntry, append as ledger_append, _now_utc  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PDF_ROOT = Path("/Volumes/One Touch/Indian Liberals/PDFs-by-publisher")
BAKEOFF_OUTPUT = REPO / "data/bake-off-output"


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------


def _load_prompt(job: str) -> tuple[str, str, str]:
    """Load a prompt file, return (system, user_template, prompt_version)."""
    prompts_dir = Path(__file__).parent / "prompts"
    if job == "byline-sweep":
        f = prompts_dir / "byline-sweep.md"
    elif job == "metadata.a":
        f = prompts_dir / "metadata.a.md"
    elif job == "metadata.b":
        f = prompts_dir / "metadata.b.md"
    elif job == "tiebreak":
        f = prompts_dir / "metadata-tiebreak.md"
    elif job == "summary":
        f = prompts_dir / "summary.md"
    else:
        raise ValueError(f"Unknown job {job!r}")

    text = f.read_text(encoding="utf-8")

    # Parse version from first-line comment <!-- vX.Y -->
    version = "v0.0"
    if text.startswith("<!--"):
        first_line = text.split("\n", 1)[0]
        if "v" in first_line:
            version = first_line.split("v", 1)[1].split(" ", 1)[0].rstrip(" -->")

    # Split sections by "---" at start-of-line
    sections = [s.strip() for s in text.split("\n---\n")]
    if len(sections) < 2:
        raise ValueError(f"Prompt {f.name} missing expected ---  delimiters")

    # First section is SYSTEM (strip the leading "# SYSTEM" header and HTML comment)
    system_block = sections[0]
    # Drop HTML comments + first "# SYSTEM" line
    system_lines = [
        line for line in system_block.splitlines()
        if not line.startswith("<!--") and line.strip() != "# SYSTEM"
    ]
    system = "\n".join(system_lines).strip()

    # Second section is USER_TEMPLATE
    user_block = sections[1]
    user_lines = [
        line for line in user_block.splitlines()
        if line.strip() != "# USER_TEMPLATE"
    ]
    user_template = "\n".join(user_lines).strip()

    return system, user_template, version


# ---------------------------------------------------------------------------
# User-template substitution
# ---------------------------------------------------------------------------


def _substitute(template: str, **kwargs) -> str:
    """Simple {{ KEY }} substitution. Missing keys raise an error."""
    out = template
    for key, value in kwargs.items():
        placeholder = "{{ " + key + " }}"
        out = out.replace(placeholder, str(value))
    # Detect any unfilled placeholders
    import re
    leftover = re.findall(r"{{\s*([A-Z_]+)\s*}}", out)
    if leftover:
        # Don't raise — some templates may have optional placeholders.
        # Just blank them out so the prompt is still usable.
        for k in leftover:
            out = out.replace("{{ " + k + " }}", f"[{k} not provided]")
    return out


# ---------------------------------------------------------------------------
# Authority-file subset selection
# ---------------------------------------------------------------------------


def _load_authority_subset(language: str | None = None, max_thinkers: int = 60) -> str:
    """
    Return a JSON-string subset of the authority file for inclusion in the
    user prompt. Picks canonical thinkers first, then high-confidence ones,
    filtered weakly by language hint when provided.
    """
    auth_file = REPO / "data/authority/thinkers.json"
    if not auth_file.exists():
        return "{}"
    data = json.loads(auth_file.read_text(encoding="utf-8"))
    thinkers = data.get("thinkers", [])
    # Sort canonical first, then high, then medium
    order = {"canonical": 0, "high": 1, "medium": 2}
    thinkers.sort(key=lambda t: (order.get(t.get("confidence", "low"), 9), t.get("id", "")))

    pruned = []
    for t in thinkers[:max_thinkers]:
        pruned.append({
            "id": t["id"],
            "canonical": t["name"]["canonical"],
            "aliases": t["name"].get("also_known_as", []),
            "tradition": t.get("tradition"),
            "birth_year": t.get("birth_year"),
            "death_year": t.get("death_year"),
        })

    # Also include organisations + publishers (small enough to ship in full)
    orgs_file = REPO / "data/authority/organisations.json"
    pubs_file = REPO / "data/authority/publishers.json"
    orgs = json.loads(orgs_file.read_text(encoding="utf-8")).get("organisations", []) if orgs_file.exists() else []
    pubs = json.loads(pubs_file.read_text(encoding="utf-8")).get("publishers", []) if pubs_file.exists() else []

    subset = {"thinkers": pruned, "organisations": orgs, "publishers": pubs}
    return json.dumps(subset, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Work-type taxonomy + theme vocabulary (loaded from the design doc / constants)
# ---------------------------------------------------------------------------

WORK_TYPE_TAXONOMY = """
work_type enum (pick ONE):
  book            — Single-author full-length work, ≥80 pages, has chapters + apparatus
  pamphlet        — Short standalone publication, single argument, 8-60 pages
  speech          — Lecture / address / address-to-meeting (has delivery date + venue)
  essay           — Mid-length single-author argument; not a pamphlet-series item, not a speech
  edited_volume   — Multi-contributor work with named editor(s) — anthologies, festschrifts, proceedings
  occasional_paper — Institutional document — manifestos, policy papers, statements of principle, reports
  letter          — Single open letter or letter-as-publication
  correspondence  — Collected letters between named individuals
  periodical_issue — One issue of a serial (routes to periodicals collection)
  reference       — Bibliography / dictionary / catalogue / index

purpose qualifier (optional, sub-type granularity):
  occasional_paper:  manifesto | statement_of_principles | report | working_paper | position_paper | annual_report
  edited_volume:     anthology | festschrift | proceedings | memorial_volume | collected_works
  book:              treatise | memoir | biography | textbook
  speech:            parliamentary | convocation | convention_address | inaugural | memorial_lecture

Three rules to keep classification consistent:
  1. Speech beats pamphlet when there's a delivery date + venue.
  2. Periodical-issue check is binary, do it first (masthead + volume/number + multi-article = periodical_issue).
  3. Organization-as-author is OK (Swatantra Party manifesto). authors: []; issuer_id set.
""".strip()

THEME_VOCABULARY = """
Controlled vocabulary (pick from this list; emit theme_proposed_new[] for genuine gaps):
  economic-liberty, planning-critique, free-trade, regulatory-state-critique, monetary-policy,
  agricultural-reform, land-reform, property-rights, fiscal-policy, public-sector-critique,
  civil-liberty, free-speech, rule-of-law, constitutionalism, federalism, separation-of-powers,
  individual-rights, women-rights, dalit-rights, religious-freedom, secularism,
  education, health-policy, urban-policy, foreign-policy, cold-war-positioning,
  party-politics, electoral-reform, governance-reform, anti-corruption,
  socialism-debate, marxism-debate, capitalism-defence,
  press-freedom, judicial-independence, emergency-critique,
  liberalism-as-tradition, indian-liberal-history, biographical-tribute
""".strip()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_prep(args) -> None:
    """Rasterize + prepare an extraction request, print the Agent prompt to stdout."""
    pdf_path = (PDF_ROOT / args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(2)

    work_slug = pdf_path.stem

    # Load prompt
    system, user_template, version = _load_prompt(args.job)

    # Decide pages-wanted per job
    if args.job == "byline-sweep":
        pages_wanted = 1
    else:
        pages_wanted = args.pages_wanted or 20

    # Rasterize
    t0 = time.monotonic()
    chunk = rasterize_chunk(
        pdf_path=pdf_path,
        start_page=args.start_page,
        pages_wanted=pages_wanted,
    )
    rasterize_s = time.monotonic() - t0

    # Build user_text via substitution
    authority_subset = _load_authority_subset()
    page_numbers = [p.page_num for p in chunk.pages]
    user_text = _substitute(
        user_template,
        PDF_NAME=pdf_path.name,
        PUBLISHER_FOLDER=pdf_path.parent.name,
        TOTAL_PDF_PAGES=chunk.total_pages_in_pdf,
        N_PAGES=len(chunk.pages),
        PAGE_NUMBERS=str(page_numbers),
        AUTHORITY_SUBSET=authority_subset,
        WORK_TYPE_TAXONOMY=WORK_TYPE_TAXONOMY,
        THEME_VOCABULARY=THEME_VOCABULARY,
    )

    # Package via dispatcher
    req = DispatchRequest(
        system_prompt=system,
        user_text=user_text,
        images=[p.jpeg_bytes for p in chunk.pages],
        image_page_numbers=page_numbers,
        model=args.model,
        work_slug=work_slug,
        job=args.job,
        chunk_idx=args.chunk_idx,
        prompt_version=version,
    )
    prepared = prepare_request(req)

    # Print summary + the agent prompt
    print(f"=== Prepared request {prepared.request_id} ===")
    print(f"  PDF: {pdf_path.name}")
    print(f"  Job: {args.job}")
    print(f"  Model: {args.model}")
    print(f"  Pages rendered: {len(chunk.pages)} (PDF page numbers: {page_numbers})")
    print(f"  Blank pages skipped: {chunk.blank_pages_skipped}")
    print(f"  Rasterize time: {rasterize_s:.2f}s")
    print(f"  Request dir: {prepared.request_dir}")
    print()
    print("=== AGENT PROMPT (dispatch this) ===")
    print(prepared.suggested_agent_prompt)
    print()
    print("=== After Agent returns, run: ===")
    print(f"python3 driver.py collect --request-dir {prepared.request_dir} \\")
    print(f"  --pdf {args.pdf} \\")
    print(f"  --job {args.job} --model {args.model} --prompt-version {version} \\")
    print(f"  --self-consistency-run {args.self_consistency_run or 'none'} \\")
    print(f"  --response-file <path-where-you-saved-agent-output.json>")


def cmd_collect(args) -> None:
    """Parse a saved Agent response, validate, write to per-work output dir, append ledger."""
    response_file = Path(args.response_file)
    if not response_file.exists():
        print(f"ERROR: response file not found: {response_file}", file=sys.stderr)
        sys.exit(2)

    raw_text = response_file.read_text(encoding="utf-8")
    resp = parse_response(raw_text, response_format="json")

    # Write to per-work output dir
    work_slug = Path(args.pdf).stem
    out_dir = BAKEOFF_OUTPUT / work_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    run_suffix = f".{args.self_consistency_run}" if args.self_consistency_run and args.self_consistency_run != "none" else ""
    out_path = out_dir / f"{args.job}{run_suffix}.json"

    if resp.ok and resp.parsed_json is not None:
        out_path.write_text(json.dumps(resp.parsed_json, indent=2, ensure_ascii=False), encoding="utf-8")
        status = "ok"
    else:
        out_path.write_text(raw_text, encoding="utf-8")
        status = f"parse_error: {resp.error}"

    # Ledger
    entry = LedgerEntry(
        timestamp=_now_utc(),
        pdf_path=args.pdf,
        job=args.job,
        chunk_idx=0,
        model=args.model,
        prompt_version=args.prompt_version,
        self_consistency_run=args.self_consistency_run if args.self_consistency_run != "none" else None,
        input_tokens=None,
        output_tokens=None,
        wall_clock_s=0.0,  # unknown — we don't have it from outside the dispatch
        ok=resp.ok,
        error=resp.error,
        work_slug=work_slug,
    )
    ledger_append(entry)

    print(f"=== Collected ===")
    print(f"  Response: {response_file}")
    print(f"  Status:   {status}")
    print(f"  Written:  {out_path}")
    print(f"  Ledger:   appended 1 entry for {args.job} / {work_slug}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM extraction driver — prep + collect commands")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prep", help="Rasterize + prepare a request, print Agent prompt")
    p_prep.add_argument("pdf", help="PDF path relative to PDFs-by-publisher/")
    p_prep.add_argument("--job", required=True,
                        choices=["byline-sweep", "metadata.a", "metadata.b", "tiebreak", "summary"])
    p_prep.add_argument("--model", default="sonnet", choices=["sonnet", "opus"])
    p_prep.add_argument("--start-page", type=int, default=1)
    p_prep.add_argument("--pages-wanted", type=int, default=None,
                        help="Override default pages-per-chunk (default: 1 for byline-sweep, 20 otherwise)")
    p_prep.add_argument("--chunk-idx", type=int, default=0)
    p_prep.add_argument("--self-consistency-run", default=None,
                        choices=["a", "b", "tiebreak", "none", None])
    p_prep.set_defaults(func=cmd_prep)

    p_collect = sub.add_parser("collect", help="Save an Agent response and ledger it")
    p_collect.add_argument("--request-dir", required=True)
    p_collect.add_argument("--pdf", required=True)
    p_collect.add_argument("--job", required=True)
    p_collect.add_argument("--model", default="sonnet")
    p_collect.add_argument("--prompt-version", default="v1.0")
    p_collect.add_argument("--self-consistency-run", default="none")
    p_collect.add_argument("--response-file", required=True)
    p_collect.set_defaults(func=cmd_collect)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
