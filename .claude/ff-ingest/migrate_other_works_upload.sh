#!/bin/zsh
# Uploads every file in /tmp/other_works_manifest.tsv (local\tkey\tmdfile\told_url\tnew_url)
# to the indianliberals-archive R2 bucket, under the same key as its existing
# WordPress path. Parallel, 8 at a time. Idempotent: re-running just re-uploads
# (cheap, since these are small PDFs) — safe to re-run on partial failure.
TSV="/tmp/other_works_manifest.tsv"
LOG="/tmp/other_works_upload.log"
: > "$LOG"
cd "/Users/siraj/Indian Liberals Website"
MAX=8; n=0
while IFS=$'\t' read -r local key mdfile old_url new_url; do
  (
    if npx wrangler r2 object put "indianliberals-archive/${key}" --file "${local}" --content-type application/pdf --remote >/dev/null 2>>"$LOG"; then
      echo "OK  ${key}" >> "$LOG"
    else
      echo "FAIL ${key}" >> "$LOG"
    fi
  ) &
  n=$((n+1))
  if (( n % MAX == 0 )); then wait; fi
done < "$TSV"
wait
echo "=== upload loop done ==="
echo "OK=$(grep -c '^OK ' "$LOG")  FAIL=$(grep -c '^FAIL ' "$LOG")"
