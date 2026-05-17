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
from validator import validate_metadata  # noqa: E402

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

    # For summary jobs, also load the metadata.a output (or .b, whichever
    # exists — they agree on the structural fields) so the summarisation
    # prompt has the work_type, language, TOC, contributors etc. that it
    # needs to branch on (single-author vs multi-author shape).
    metadata_json = "{}"
    if args.job == "summary":
        bake_out_dir = BAKEOFF_OUTPUT / work_slug
        for candidate in ("metadata.a.a.json", "metadata.b.b.json", "metadata.a.json", "metadata.b.json"):
            p = bake_out_dir / candidate
            if p.exists():
                metadata_json = p.read_text(encoding="utf-8")
                break

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
        METADATA_JSON=metadata_json,
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
        # Apply post-extraction validator (force-null bad enum values + unknown
        # thinker_ids, fix confidence nulls, stamp _validator audit block).
        # Only meaningful for metadata + summary jobs; byline-sweep doesn't
        # carry the enum/thinker fields that the validator polices.
        if args.job in {"metadata.a", "metadata.b", "tiebreak", "summary"}:
            validated = validate_metadata(resp.parsed_json)
            out_path.write_text(json.dumps(validated, indent=2, ensure_ascii=False), encoding="utf-8")
            v = validated.get("_validator", {})
            corr = v.get("corrections", [])
            status = "ok" + (f" ({len(corr)} validator corrections)" if corr else "")
        else:
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


# ---------------------------------------------------------------------------
# Loop helpers (continuation loop — D1, D5, D12, D13, D14 per design doc)
# ---------------------------------------------------------------------------

def _same_toc_set(entries_a: list, entries_b: list) -> bool:
    """
    D13 / loop guard — check set equality on toc_index across two lists
    of TOC entry dicts. Used by the no-progress guard.
    """
    def _idx_set(entries):
        return {
            e.get("toc_index")
            for e in entries
            if isinstance(e, dict) and e.get("toc_index") is not None
        }
    return _idx_set(entries_a) == _idx_set(entries_b)


def _build_virtual_toc(pages_total: int, author_id: str | None = None) -> list[dict]:
    """
    D13 — Build a synthetic 20-page-window TOC for thick single-author works
    that have no formal TOC. Virtual entries are flagged with virtual: true
    so editorial knows these are page-window summaries, not editorial divisions.
    """
    import math
    n_windows = math.ceil(pages_total / 20)
    entries = []
    for i in range(n_windows):
        page_start = i * 20 + 1
        page_end = min((i + 1) * 20, pages_total)
        entries.append({
            "toc_index": i,
            "title": f"pages {page_start}–{page_end}",
            "byline_verbatim": None,
            "thinker_id_proposed": author_id,
            "page_start": page_start,
            "page_end": page_end,
            "page_system": "pdf",
            "complete_in_chunk": (i == 0),
            "seen_through_page": page_end if i == 0 else None,
            "virtual": True,
        })
    return entries


def _build_initial_record(meta_final: dict, sum_chunk0: dict) -> dict:
    """
    Merge chunk-0 metadata + summary outputs into the canonical running record.
    The record is the single source of truth that accumulates across the loop.
    """
    import copy
    record = copy.deepcopy(meta_final)

    # Carry over summary fields
    for key in ("summary", "volume_summary", "extent_caveat",
                "summary_structured", "essays_summarized",
                "summary_completeness", "recommended_authority_additions"):
        if key in sum_chunk0:
            record[key] = sum_chunk0[key]

    # Initialise continuation-loop tracking fields
    record.setdefault("toc_drift_detected", False)
    record.setdefault("dispatch_count", 0)
    record.setdefault("needs_human_review", False)

    return record


def _merge_essay_into_record(record: dict, essay_summary: dict, toc_index: int) -> dict:
    """
    Append-only merge of one essay_summary into record.essays_summarized[].
    If a prior entry for the same toc_index exists (partial from chunk 0),
    it is REPLACED by the new entry (the "later wins on same toc_index" rule).
    """
    essays = record.setdefault("essays_summarized", [])
    # Remove any existing entry for this toc_index
    record["essays_summarized"] = [e for e in essays if e.get("toc_index") != toc_index]
    # Ensure toc_index is set in the essay summary
    essay_summary = dict(essay_summary)
    essay_summary["toc_index"] = toc_index
    record["essays_summarized"].append(essay_summary)

    # Mark this entry as no longer pending in toc.entries_not_yet_rendered
    toc = record.setdefault("toc", {})
    not_yet = toc.get("entries_not_yet_rendered") or []
    toc["entries_not_yet_rendered"] = [
        e for e in not_yet
        if not (isinstance(e, dict) and e.get("toc_index") == toc_index)
    ]
    return record


def _sub_chunk_essay(entry: dict, max_pages: int = 20) -> list[dict]:
    """
    Split a TOC entry's page range into ≤max_pages sub-chunks.
    Returns a list of dicts with page_start, page_end.
    """
    page_start = entry.get("page_start")
    page_end = entry.get("page_end")
    if page_start is None:
        return [entry]  # can't sub-chunk without page_start
    if page_end is None or (page_end - page_start + 1) <= max_pages:
        return [{"page_start": page_start, "page_end": page_end or (page_start + max_pages - 1)}]

    sub_chunks = []
    current = page_start
    while current <= page_end:
        end = min(current + max_pages - 1, page_end)
        sub_chunks.append({"page_start": current, "page_end": end})
        current = end + 1
    return sub_chunks


# ---------------------------------------------------------------------------
# Loop command
# ---------------------------------------------------------------------------


def cmd_loop(args) -> None:
    """
    Continuation loop for one PDF — assembles the final v1.2 record from
    already-dispatched-and-collected chunk outputs.

    The orchestrator (main Claude Code session) is responsible for running
    `driver.py prep` + dispatch + `driver.py collect` for each chunk.
    This command reads those collected outputs from a directory and merges
    them into the final record.

    Workflow:
      --dry-run (default):
          Reads chunk 0 outputs from the bake-off-output directory and prints
          a dispatch plan listing all continuation chunks the orchestrator
          should dispatch.
      --from-collected-chunks <dir>:
          Reads all chunk outputs from <dir>, applies the merge logic
          (essays_summarized[], D14 drift detection, D5 extent_caveat,
          D13 virtual TOC, D1 pages_rendered), validates, and writes
          <output-dir>/<slug>/final.json.
    """
    import math
    import glob

    from validator import validate_metadata, detect_toc_drift

    output_dir = Path(args.output_dir) if args.output_dir else BAKEOFF_OUTPUT

    # ----------------------------------------------------------------
    # Resolve PDF slug
    # ----------------------------------------------------------------
    pdf_rel = args.pdf
    work_slug = Path(pdf_rel).stem
    work_out = output_dir / work_slug
    work_out.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------
    # Load chunk 0 outputs
    # ----------------------------------------------------------------
    def _load_json(path: Path) -> dict | None:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f"  WARNING: JSON parse error in {path}", file=sys.stderr)
        return None

    # Pick the best available metadata record
    meta_final = None
    for candidate in ("tiebreak.json", "metadata.a.a.json", "metadata.b.b.json",
                      "metadata.a.json", "metadata.b.json"):
        m = _load_json(work_out / candidate)
        if m is not None:
            meta_final = m
            print(f"  Loaded metadata from: {candidate}")
            break

    if meta_final is None:
        print(f"ERROR: No metadata found in {work_out}. Run prep+collect for chunk 0 first.",
              file=sys.stderr)
        sys.exit(2)

    # Load chunk 0 summary
    sum_chunk0 = _load_json(work_out / "summary.json") or {}

    # ----------------------------------------------------------------
    # Build initial record
    # ----------------------------------------------------------------
    record = _build_initial_record(meta_final, sum_chunk0)

    # ----------------------------------------------------------------
    # D13 — Virtual TOC for thick single-author no-TOC works
    # ----------------------------------------------------------------
    toc = record.get("toc") or {}
    toc_entries = toc.get("entries") or []
    pages_total = (record.get("physical") or {}).get("pages_total")
    work_type = record.get("work_type", "")
    if (
        work_type in {"book", "essay", "occasional_paper"}
        and pages_total
        and pages_total > 60
        and not toc_entries
    ):
        authors = record.get("authors") or []
        author_id = authors[0].get("thinker_id") if authors else None
        virtual_entries = _build_virtual_toc(pages_total, author_id)
        record["toc"] = record.get("toc") or {}
        record["toc"]["entries"] = virtual_entries
        record["toc"]["entries_not_yet_rendered"] = virtual_entries[1:]  # window 0 = chunk 0
        record["toc"]["virtual_toc_generated"] = True
        print(f"  D13: Generated virtual TOC ({len(virtual_entries)} windows of ≤20 pages)")
        toc_entries = virtual_entries

    # ----------------------------------------------------------------
    # --dry-run: print dispatch plan and exit
    # ----------------------------------------------------------------
    if not args.from_collected_chunks:
        not_yet = record.get("toc", {}).get("entries_not_yet_rendered") or []
        print()
        print(f"=== Dry-run dispatch plan for {work_slug} ===")
        print(f"  Work type: {record.get('work_type')}")
        print(f"  Pages total: {pages_total}")
        print(f"  TOC entries not yet rendered: {len(not_yet)}")
        print()
        if not not_yet:
            print("  No continuation chunks needed — chunk 0 covers the full work.")
        else:
            iteration_ceiling = math.ceil((pages_total or 200) / 20) + 2
            print(f"  Iteration ceiling: {iteration_ceiling}")
            print(f"  Max dispatches allowed: {args.max_dispatches}")
            print()
            print("  Dispatch plan:")
            budget = args.max_dispatches
            # Build a lookup from toc_index -> full entry dict for integer-shorthand entries
            all_entries_list = (record.get("toc") or {}).get("entries") or []
            toc_entry_map = {
                e.get("toc_index"): e
                for e in all_entries_list
                if isinstance(e, dict) and e.get("toc_index") is not None
            }
            for i, entry in enumerate(not_yet[:min(len(not_yet), budget)]):
                # Handle integer-shorthand entries (list of toc_index ints)
                if isinstance(entry, int):
                    entry = toc_entry_map.get(entry, {"toc_index": entry})
                if isinstance(entry, dict):
                    sub_chunks = _sub_chunk_essay(entry, max_pages=20)
                    for j, sc in enumerate(sub_chunks):
                        chunk_label = f"chunk_{i+1}" + (f"_sub{j}" if len(sub_chunks) > 1 else "")
                        ps = sc.get("page_start", "?")
                        pe = sc.get("page_end", "?")
                        print(f"    [{chunk_label}] toc_index={entry.get('toc_index')}  "
                              f"pages {ps}-{pe}  "
                              f"job=summary (essay_focused mode)")
                        budget -= 1
                    if len(sub_chunks) > 1:
                        print(f"    [{chunk_label}_synthesis] essay-synthesis call")
                        budget -= 1
                if budget <= 0:
                    print(f"    [TRUNCATED -- dispatch budget {args.max_dispatches} would be exceeded]")
                    break
        print()
        print("Run with --from-collected-chunks <dir> after dispatching all chunks.")
        return

    # ----------------------------------------------------------------
    # --from-collected-chunks: load + merge essay chunks
    # ----------------------------------------------------------------
    chunks_dir = Path(args.from_collected_chunks)
    if not chunks_dir.exists():
        print(f"ERROR: chunks directory not found: {chunks_dir}", file=sys.stderr)
        sys.exit(2)

    # Find all essay chunk outputs: summary.chunk_N.json or essay.N.json etc.
    # Convention: files named essay.<toc_index>.json or summary.chunk_<N>.json
    essay_files = sorted(
        list(chunks_dir.glob("essay.*.json"))
        + list(chunks_dir.glob("summary.chunk_*.json"))
    )

    if not essay_files:
        print(f"  No essay chunk files found in {chunks_dir}")
        print(f"  Expected: essay.<toc_index>.json or summary.chunk_<N>.json")
    else:
        print(f"  Found {len(essay_files)} essay chunk file(s)")

    dispatch_budget = args.max_dispatches
    drift_check_done = False
    prev_unrendered = list(record.get("toc", {}).get("entries_not_yet_rendered") or [])
    chunks_with_no_progress = 0
    pages_total = (record.get("physical") or {}).get("pages_total") or 200
    iteration_ceiling = math.ceil(pages_total / 20) + 2

    for chunk_path in essay_files:
        if dispatch_budget <= 0:
            record["needs_human_review"] = True
            record["failure"] = "dispatch_budget_exceeded"
            break

        essay_summary = _load_json(chunk_path)
        if essay_summary is None:
            print(f"  WARNING: Could not load {chunk_path}")
            continue

        toc_index = essay_summary.get("toc_index")
        if toc_index is None:
            print(f"  WARNING: No toc_index in {chunk_path.name} — skipping")
            continue

        # Merge into record
        record = _merge_essay_into_record(record, essay_summary, toc_index)
        dispatch_budget -= 1

        # D14 — TOC drift check (once, on first essay chunk)
        if not drift_check_done:
            drift_check_done = True
            toc_all_entries = (record.get("toc") or {}).get("entries") or []
            if detect_toc_drift(toc_all_entries, essay_summary):
                record["toc_drift_detected"] = True
                record["needs_human_review"] = True
                print(f"  D14: TOC drift detected on toc_index={toc_index}. "
                      f"Flag set — orchestrator should dispatch metadata-tiebreak.")

        # No-progress guard
        new_unrendered = (record.get("toc") or {}).get("entries_not_yet_rendered") or []
        if _same_toc_set(prev_unrendered, new_unrendered):
            chunks_with_no_progress += 1
            if chunks_with_no_progress >= 2:
                record["needs_human_review"] = True
                record["failure"] = "continuation_loop_no_progress"
                print("  WARNING: No-progress guard triggered — loop halted.")
                break
        else:
            chunks_with_no_progress = 0
        prev_unrendered = list(new_unrendered)

    # ----------------------------------------------------------------
    # D5 — extent_caveat
    # ----------------------------------------------------------------
    phys = record.get("physical") or {}
    pages_rendered = phys.get("pages_rendered") or phys.get("page_count_visible") or 0
    pages_total_val = phys.get("pages_total") or 0
    if pages_total_val > 0 and pages_rendered > 0:
        ratio = pages_rendered / pages_total_val
        if ratio < 0.3:
            record["extent_caveat"] = True

    # ----------------------------------------------------------------
    # D1 — Set cumulative pages_rendered from essays_summarized
    # ----------------------------------------------------------------
    # Count unique pages across all essays (approximation: sum of seen ranges)
    covered_pages: set[int] = set()
    for essay in (record.get("essays_summarized") or []):
        ss = essay.get("summary_structured") or {}
        completeness = ss.get("summary_completeness") or {}
        based_on = completeness.get("based_on_pages") or []
        if len(based_on) == 2:
            try:
                for p in range(int(based_on[0]), int(based_on[1]) + 1):
                    covered_pages.add(p)
            except (TypeError, ValueError):
                pass
    if covered_pages:
        total_rendered = max(covered_pages) - min(covered_pages) + 1
        record.setdefault("physical", {})["pages_rendered"] = total_rendered

    # ----------------------------------------------------------------
    # Track dispatch count
    # ----------------------------------------------------------------
    record["dispatch_count"] = args.max_dispatches - dispatch_budget

    # ----------------------------------------------------------------
    # Validate + write final record
    # ----------------------------------------------------------------
    validated = validate_metadata(record)
    final_path = work_out / "final.json"
    final_path.write_text(json.dumps(validated, indent=2, ensure_ascii=False), encoding="utf-8")

    v = validated.get("_validator", {})
    corr_count = len(v.get("corrections", []))
    print()
    print(f"=== Loop complete for {work_slug} ===")
    print(f"  Essays summarized: {len(record.get('essays_summarized', []))}")
    print(f"  Entries not yet rendered: {len((record.get('toc') or {}).get('entries_not_yet_rendered') or [])}")
    print(f"  Dispatch count: {record.get('dispatch_count')}")
    print(f"  Extent caveat: {record.get('extent_caveat', False)}")
    print(f"  TOC drift detected: {record.get('toc_drift_detected', False)}")
    print(f"  Needs human review: {record.get('needs_human_review', False)}")
    print(f"  Validator: {corr_count} corrections, ok={v.get('ok')}")
    print(f"  Written: {final_path}")


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

    p_loop = sub.add_parser(
        "loop",
        help=(
            "Assemble final v1.2 record from collected chunk outputs. "
            "In --dry-run mode (default), prints the dispatch plan. "
            "In --from-collected-chunks mode, merges chunks into final.json."
        ),
    )
    p_loop.add_argument(
        "pdf",
        help="PDF path relative to PDFs-by-publisher/ (used to derive work_slug)",
    )
    p_loop.add_argument(
        "--max-dispatches", type=int, default=80,
        help="Hard ceiling on subagent calls per work (default: 80)",
    )
    p_loop.add_argument(
        "--max-iterations", type=int, default=None,
        help="Override iteration ceiling (default: derived from pages_total)",
    )
    p_loop.add_argument(
        "--output-dir", default=None,
        help=f"Directory for output files (default: {BAKEOFF_OUTPUT})",
    )
    p_loop.add_argument(
        "--from-collected-chunks", default=None, metavar="DIR",
        help=(
            "Directory containing collected essay chunk JSON files "
            "(essay.<toc_index>.json or summary.chunk_<N>.json). "
            "When provided, merges chunks into final.json. "
            "When omitted, runs in dry-run mode and prints the dispatch plan."
        ),
    )
    p_loop.set_defaults(func=cmd_loop)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
