#!/bin/zsh
# Collect one Quest issue's agent outputs, emit its markdown, and apply the
# repo's guards. The agent produces a COMPLETE full-issue summary, so there is
# no chunk merge: summary.json is final.
set -e
REPO="/Users/siraj/Indian Liberals Website"
export LLM_EXTRACT_PDF_ROOT="/tmp/quest-scans"
cd "$REPO"
QT="$1"; DIR="$2"; V=".venv-extract/bin/python"
slug=$(echo "$QT" | tr 'A-Z' 'a-z')
for f in response_metadata.json response_summary.json; do
  [ -s "$DIR/$f" ] || { echo "MISSING $QT $f"; exit 2; }
  $V -c "import json;json.load(open('$DIR/$f'))" || { echo "INVALID JSON $QT $f"; exit 3; }
done
rm -f "apps/site/src/content/primary-works/${slug}.md"
LLM_EXTRACT_NO_EMIT=1 $V scripts/llm-extract/driver.py collect --request-dir "$DIR" \
  --pdf "quest/${QT}.pdf" --job metadata.a --model sonnet --prompt-version 1.5 \
  --self-consistency-run none --response-file "$DIR/response_metadata.json" 2>&1 \
  | grep -E "Status:|Error" | sed "s/^/  $QT meta /"
$V scripts/llm-extract/driver.py collect --request-dir "$DIR" \
  --pdf "quest/${QT}.pdf" --job summary --model sonnet --prompt-version 1.2 \
  --self-consistency-run none --response-file "$DIR/response_summary.json" 2>&1 \
  | grep -E "Status:|Astro MD:|Error" | sed "s/^/  $QT summ /"

# the masthead is all-caps display type, so agents transcribe both "QUEST" and
# "Quest"; the archive renders periodical titles in title case and
# periodicals.ts matches the series name, so the run must be uniform
python3 - "$slug" <<'PY'
import re, sys
from pathlib import Path
p = Path("/Users/siraj/Indian Liberals Website/apps/site/src/content/primary-works") / f"{sys.argv[1]}.md"
if p.exists():
    t = p.read_text(encoding="utf-8")
    t = re.sub(r'^(\s*main:\s*)"?QUEST"?\s*$', r'\1Quest', t, count=1, flags=re.M)
    t = re.sub(r'^(\s*publisher_id:).*$', r'\1 quest', t, count=1, flags=re.M)
    t = re.sub(r'^(\s*issuer_id:).*$', r'\1 quest', t, count=1, flags=re.M)
    t = re.sub(r'^(authors|editors|related_thinkers):\s*$(?!\n\s+-)', r'\1: []', t, flags=re.M)
    p.write_text(t, encoding="utf-8"); print(f"  normalised {p.name}")
PY
python3 scripts/synthesis/guard-byline-aliases.py --fix "$QT"
python3 .claude/quest-ingest/carry_scan_defects.py "$QT"
