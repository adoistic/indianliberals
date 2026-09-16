#!/bin/zsh
# Archive a batch's three deliverables INTO THE REPO, then remove working dirs.
#
# Order matters twice over. Once because batch 5's prep deleted QT016's dir while
# its agent was still writing deliverable 3. And once because the whole harvest
# was previously kept in the session scratchpad, which a disk-full event wiped —
# 20 issues of contributor notes gone. Contributor notes now land in
# data/quest-contributors/ and are committed.
REPO="/Users/siraj/Indian Liberals Website"
OUT="$REPO/data/quest-contributors"
mkdir -p "$OUT"
rc=0
for q in "$@"; do
  dir=$(ls -d /tmp/llm-extract-requests/metadata.a/${q}-chunk0-* 2>/dev/null | head -1)
  [ -z "$dir" ] && { echo "$q: no working dir"; continue; }
  if [ -s "$dir/response_contributors.json" ]; then
    cp "$dir/response_contributors.json" "$OUT/${q}.json"
  fi
  missing=""
  for f in response_metadata.json response_summary.json; do
    [ -s "$dir/$f" ] || missing="$missing $f"
  done
  [ -s "$OUT/${q}.json" ] || missing="$missing contributors"
  if [ -n "$missing" ]; then
    echo "$q: KEEPING working dir — missing:$missing"; rc=1
  else
    rm -rf "$dir"; echo "$q: archived to data/quest-contributors/${q}.json, working dir removed"
  fi
done
exit $rc
