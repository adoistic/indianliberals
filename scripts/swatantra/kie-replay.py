#!/usr/bin/env python3
"""Replay already-extracted Swatantra works through kie.ai and diff the result.

Purpose is A/B, not production: every work this touches must ALREADY have a
baked record under data/bake-off-output/, so each kie response has a Sonnet
baseline to be scored against. Works with no baseline are skipped rather than
extracted — an unscored record tells us nothing and costs money.

kie's Claude surface is Anthropic-native (`/claude/v1/messages`, auth via
`Authorization: Bearer`), so the request shape is byte-identical to what
driver.py already builds — same system prompt, same page JPEGs, same
cache_control breakpoint. That is the point: any output difference is the
provider's, not ours.

Two provider quirks this records rather than hides:
  - kie prepends ~25k tokens we did not send (visible as cache_read on a
    request carrying no system prompt). Every usage block is saved so the
    overhead is measurable rather than assumed.
  - the served model string comes back effort-suffixed (`-medium`), so the
    baseline may not be the same effort. Saved verbatim for the same reason.

    python3 scripts/swatantra/kie-replay.py run --n 5
    python3 scripts/swatantra/kie-replay.py report
"""
import argparse
import base64
import csv
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORPUS = ("/Users/siraj/Library/CloudStorage/GoogleDrive-adnan@thothica.com/"
          ".shortcut-targets-by-id/1vDrOqgdnQHTfL5vqJtx-ZRy4e2jf-Bcq/"
          "Swatantra Party papers")
BAKE = REPO / "data/bake-off-output"
INVENTORY = REPO / "data/swatantra-papers/inventory.tsv"
PIN_THINKERS = REPO / "data/swatantra-papers/pin-thinkers.json"
ADDENDUM = REPO / "scripts/llm-extract/prompts/metadata-weak-model-addendum.md"
OUT = REPO / "data/swatantra-papers/kie-replay"
VENV = REPO / ".venv-extract/bin/python3"
DRIVER = REPO / "scripts/llm-extract/driver.py"
# kie exposes two different upstreams, and they are NOT the same API.
#   anthropic -> /claude/v1/messages   Anthropic Messages shape, base64 images
#   codex     -> /codex/v1/responses   OpenAI *Responses* shape (not
#                chat/completions), dash-form model ids, data: URI images,
#                and a Codex coding-agent prompt in `instructions` unless we
#                override it — which we do, with our real system prompt.
ENDPOINT_ANTHROPIC = "https://api.kie.ai/claude/v1/messages"
ENDPOINT_CODEX = "https://api.kie.ai/codex/v1/responses"


def api_key():
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("KIE_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("KIE_API_KEY not found in .env")


def _band(n):
    return ("1pp" if n == 1 else "2pp" if n == 2 else "3-5pp"
            if n <= 5 else "6-20pp" if n <= 20 else "21+pp")


def baked_candidates(pages=1):
    """Swatantra works that already have BOTH self-consistency records."""
    inv = {os.path.splitext(r["file"])[0]: r
           for r in csv.DictReader(open(INVENTORY, encoding="utf-8"), delimiter="\t")}
    out = []
    for sub in sorted(BAKE.iterdir()):
        if not sub.is_dir() or sub.name not in inv:
            continue
        if not ((sub / "metadata.a.a.json").exists()
                and (sub / "metadata.b.b.json").exists()):
            continue
        if pages is None or int(inv[sub.name]["pages"]) == pages:
            out.append(inv[sub.name]["file"])
    return out


def stratified(n):
    """Spread the sample across page bands AND Sonnet-assigned work_types.

    The 1-page-letter sample flattered the challenger: those are the easiest
    documents in the corpus. Telegrams are only 2.2% of works but are where
    the observed failures concentrate, so they get pulled in deliberately
    rather than left to chance — a 40-work random draw would expect one.
    Both Sonnet passes must agree on the work_type before it is used as a
    stratum label, otherwise the label is itself noise.
    """
    inv = {os.path.splitext(r["file"])[0]: r
           for r in csv.DictReader(open(INVENTORY, encoding="utf-8"), delimiter="\t")}
    pool = []
    for f in baked_candidates(pages=None):
        slug = Path(f).stem
        try:
            a = json.loads((BAKE / slug / "metadata.a.a.json").read_text(encoding="utf-8"))
            b = json.loads((BAKE / slug / "metadata.b.b.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        wt = a.get("work_type")
        if wt != b.get("work_type"):
            continue
        pool.append((f, _band(int(inv[slug]["pages"])), wt))

    # round-robin across (band, work_type) cells so no cell dominates
    cells = {}
    for f, band, wt in pool:
        cells.setdefault((band, wt), []).append(f)
    # rare-but-important types first: they are the ones under test
    order = sorted(cells, key=lambda k: (len(cells[k]), k))
    picked, i = [], 0
    while len(picked) < n and any(cells.values()):
        k = order[i % len(order)]
        if cells[k]:
            picked.append(cells[k].pop(0))
        i += 1
        if i > len(order) * 200:
            break
    return picked


def prep(pdf_name, job):
    """driver.py prep — rasterise + substitute prompts. Returns request dir."""
    # The baked baseline was produced with the 28 pinned authority ids in
    # scope (LLM_EXTRACT_PIN_THINKERS_FILE). Omitting it here silently drops
    # Masani et al from the authority subset, and the binary resolution rule
    # then makes `thinker_id: null` the CORRECT answer — which reads as a
    # model quality failure when it is really a harness mismatch. Any A/B has
    # to hand both sides the same resolution universe.
    env = dict(os.environ, LLM_EXTRACT_PDF_ROOT=CORPUS,
               LLM_EXTRACT_PIN_THINKERS_FILE=str(PIN_THINKERS))
    r = subprocess.run(
        [str(VENV), str(DRIVER), "prep", pdf_name, "--job", job,
         "--pages-wanted", "20"],
        capture_output=True, text=True, cwd=str(REPO), env=env, timeout=300)
    for line in r.stdout.splitlines():
        if "Request dir:" in line:
            return Path(line.split("Request dir:")[1].strip())
    print(r.stderr[-500:], file=sys.stderr)
    return None


def _body_anthropic(system_text, user_text, images, model):
    content = [{"type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg",
                           "data": base64.b64encode(b).decode()}}
               for b in images]
    content.append({"type": "text", "text": user_text})
    return json.dumps({
        "model": model, "max_tokens": 8000,
        # Breakpoint on the system block: the ~20KB stable prefix shared by
        # every request of this job type, and whether kie honours it is what
        # the cost model rests on.
        "system": [{"type": "text", "text": system_text,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": content}],
    }).encode()


def _body_codex(system_text, user_text, images, model, effort):
    content = [{"type": "input_image",
                "image_url": "data:image/jpeg;base64," + base64.b64encode(b).decode()}
               for b in images]
    content.append({"type": "input_text", "text": user_text})
    return json.dumps({
        "model": model, "stream": False,
        "instructions": system_text,   # replaces kie's default Codex prompt
        "input": [{"role": "user", "content": content}],
        "reasoning": {"effort": effort},
    }).encode()


def _unwrap(route, payload):
    """Normalise both upstreams to (text, usage, served_model, stop)."""
    if route == "anthropic":
        return ("".join(b.get("text", "") for b in payload.get("content", [])),
                payload.get("usage"), payload.get("model"), payload.get("stop_reason"))
    text = "".join(c.get("text", "")
                   for o in payload.get("output", []) if o.get("type") == "message"
                   for c in o.get("content", []))
    return text, payload.get("usage"), payload.get("model"), payload.get("status")


def post(route, system_text, user_text, images, model, key, effort, attempts=5):
    if route == "anthropic":
        url, body = ENDPOINT_ANTHROPIC, _body_anthropic(system_text, user_text, images, model)
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                   "anthropic-version": "2023-06-01"}
    else:
        url, body = ENDPOINT_CODEX, _body_codex(system_text, user_text, images, model, effort)
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    last = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(min(5 * 2 ** attempt, 90))
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                payload = json.loads(r.read().decode())
            text, usage, served, stop = _unwrap(route, payload)
            if text:
                payload["_norm"] = {"text": text, "usage": usage,
                                    "served": served, "stop": stop}
                return payload, attempt + 1
            last = payload.get("msg") or (payload.get("error") or {}).get("message") or "empty"
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last = str(e)
        except json.JSONDecodeError as e:
            last = f"bad json: {e}"
    return {"_failed": last}, attempts


def cmd_run(a):
    key = api_key()
    OUT.mkdir(parents=True, exist_ok=True)
    tag = a.model.replace(".", "-") + ("-add" if a.addendum else "")
    if a.works_file:
        # All jobs in a split-model trial MUST run over the same works, or the
        # per-model "already done" filter silently drifts the arms apart and
        # the merged comparison is meaningless.
        pool = json.loads(Path(a.works_file).read_text(encoding="utf-8"))
    else:
        pool = stratified(a.n * 4) if a.stratify else baked_candidates()
    todo = [f for f in pool
            if not (OUT / f"{Path(f).stem}.{a.job}.{tag}.json").exists()][:a.n]
    if not todo:
        return print("nothing to replay — all candidates already done")

    print(f"replaying {len(todo)} baked works through kie ({a.model})\n")
    for name in todo:
        slug = Path(name).stem
        d = prep(name, a.job)
        if not d:
            print(f"  PREP FAILED  {slug}")
            continue
        imgs = [p.read_bytes() for p in sorted(d.glob("page-*.jpg"))]
        sys_t = (d / "system.txt").read_text(encoding="utf-8")
        if a.addendum:
            # Appended, never substituted into the shared prompt files: the
            # baked Sonnet corpus was produced without it, and editing
            # metadata.a.md would make the two halves incomparable.
            sys_t += "\n\n---\n\n" + ADDENDUM.read_text(encoding="utf-8")
        usr_t = (d / "user.txt").read_text(encoding="utf-8")

        t0 = time.time()
        payload, tries = post(a.route, sys_t, usr_t, imgs, a.model, key, a.effort)
        secs = time.time() - t0
        n = payload.get("_norm") or {}

        rec = {
            "slug": slug, "job": a.job, "requested_model": a.model,
            "attempts": tries, "wall_clock_s": round(secs, 1),
            "prompt_bytes": {"system": len(sys_t), "user": len(usr_t)},
            "image_bytes": [len(b) for b in imgs],
            "route": a.route,
            "served_model": n.get("served"),
            "usage": n.get("usage"),
            "credits_consumed": payload.get("credits_consumed"),
            "stop_reason": n.get("stop"),
            "raw_text": n.get("text", ""),
            "failed": payload.get("_failed"),
        }
        (OUT / f"{slug}.{a.job}.{tag}.json").write_text(
            json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        shutil.rmtree(d, ignore_errors=True)  # reap pages immediately

        if rec["failed"]:
            print(f"  FAIL  {slug[:52]:52} {rec['failed'][:40]}")
        else:
            u = rec["usage"] or {}
            print(f"  ok    {slug[:46]:46} {secs:5.1f}s t={tries} "
                  f"in={u.get('input_tokens')} out={u.get('output_tokens')} "
                  f"cr={u.get('cache_read_input_tokens', 0)} "
                  f"cred={rec['credits_consumed']} {rec['served_model']}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--n", type=int, default=5)
    r.add_argument("--job", default="metadata.a")
    r.add_argument("--model", default="claude-sonnet-5")
    r.add_argument("--route", default="anthropic", choices=["anthropic", "codex"])
    r.add_argument("--effort", default="low",
                   choices=["low", "medium", "high", "xhigh"])
    r.add_argument("--works-file",
                   help="JSON array of pdf filenames; pins the sample set")
    r.add_argument("--stratify", action="store_true",
                   help="spread the sample across page bands and work types")
    r.add_argument("--addendum", action="store_true",
                   help="append the lower-capability-model prompt addendum")
    args = ap.parse_args()
    sys.exit(cmd_run(args) or 0)
