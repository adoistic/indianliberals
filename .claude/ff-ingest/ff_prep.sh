#!/bin/zsh
# Usage: ff_prep.sh <manifest_path> <FF001> <FF002> ...
# Preps metadata.a + summary for each doc; writes manifest (ff \t job \t reqdir);
# prints one dispatch line per request dir.
set -e
REPO="/Users/siraj/Indian Liberals Website"
cd "$REPO"
MANI="$1"; shift
: > "$MANI"
for ff in "$@"; do
  for job in metadata.a summary; do
    rd=$(.venv-extract/bin/python scripts/llm-extract/driver.py prep "freedom-first/${ff}.pdf" --job "$job" 2>/dev/null | grep "Request dir:" | awk '{print $3}')
    printf '%s\t%s\t%s\n' "$ff" "$job" "$rd" >> "$MANI"
  done
done
echo "PREPPED $# docs -> $(wc -l < "$MANI" | tr -d ' ') request dirs; free $(df -h /tmp | tail -1 | awk '{print $4}')"
echo "---- DISPATCH LINES (ff | job | reqdir) ----"
cat "$MANI"
