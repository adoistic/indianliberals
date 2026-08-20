#!/bin/zsh
# Usage: ff_finalize.sh <manifest_path> <batch_label>
# Collect sweep -> normalize publisher/issuer ids -> astro sync -> commit -> push -> purge /tmp.
set -e
REPO="/Users/siraj/Indian Liberals Website"
VENV="$REPO/.venv-extract/bin/python"
cd "$REPO"
MANI="$1"; LABEL="$2"

echo "=== collect sweep ==="
while IFS=$'\t' read -r ff job rd; do
  if [ ! -s "$rd/response.json" ]; then echo "MISSING response: $ff $job"; continue; fi
  out=$($VENV scripts/llm-extract/driver.py collect \
    --request-dir "$rd" --pdf "freedom-first/${ff}.pdf" \
    --job "$job" --model sonnet --prompt-version 1.4 \
    --self-consistency-run none --response-file "$rd/response.json" 2>&1)
  echo "$ff $job -> $(echo "$out" | grep -E 'Status:|Astro MD:|Error|Traceback' | tr '\n' ' ')"
done < "$MANI"

echo "=== normalize publisher_id/issuer_id on all ff*.md ==="
$VENV - <<'PY'
import glob, re
for f in sorted(glob.glob("apps/site/src/content/primary-works/ff*.md")):
    lines = open(f, encoding="utf-8").read().split("\n")
    try: s = next(i for i,l in enumerate(lines) if l == "publication:")
    except StopIteration:
        print("NO publication:", f); continue
    e = s+1
    while e < len(lines) and (lines[e].startswith(" ") or lines[e]==""): e += 1
    block = lines[s+1:e]; has_pub=has_iss=False
    for i,l in enumerate(block):
        if re.match(r'\s*publisher_id:', l): block[i]="  publisher_id: freedom-first"; has_pub=True
        elif re.match(r'\s*issuer_id:', l): block[i]="  issuer_id: freedom-first"; has_iss=True
    ins=[]
    if not has_pub: ins.append("  publisher_id: freedom-first")
    if not has_iss: ins.append("  issuer_id: freedom-first")
    if ins:
        pos=0
        for i,l in enumerate(block):
            if re.match(r'\s*language:', l): pos=i+1; break
        block[pos:pos]=ins
    new="\n".join(lines[:s+1]+block+lines[e:])
    if new != open(f,encoding="utf-8").read(): open(f,"w",encoding="utf-8").write(new)
PY

echo "=== astro sync validate ==="
( cd apps/site && timeout 180 npx astro sync 2>&1 | grep -iE "Synced content|error|invalid" | head )

echo "=== commit + push ==="
# stage only the ff*.md touched in this batch + the ledger
ids=$(awk -F'\t' '{print tolower($1)}' "$MANI" | sort -u)
for id in ${(f)ids}; do git add "apps/site/src/content/primary-works/${id}.md" 2>/dev/null; done
git add data/extraction-log.jsonl
git commit -q -m "data(primary-works): Freedom First ingestion ${LABEL}

Metadata + summary via Sonnet subagents; publisher_id/issuer_id forced to
freedom-first for series grouping. work_type: periodical_issue, needs_review.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git pull --rebase origin main 2>&1 | tail -1
git push origin main 2>&1 | tail -2
echo "HEAD: $(git log --oneline -1)"

echo "=== purge /tmp ==="
rm -rf /tmp/llm-extract-requests/*
echo "free $(df -h /tmp | tail -1 | awk '{print $4}'); total FF issues: $(ls apps/site/src/content/primary-works/ff*.md | wc -l | tr -d ' ')"
