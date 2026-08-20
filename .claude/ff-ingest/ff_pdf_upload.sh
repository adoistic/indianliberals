#!/bin/zsh
# Upload every FF scan in /tmp/ff_pdf_manifest.tsv to R2 under its date-slug key.
# Columns: local \t key \t mdfile \t url. Parallel 8. Idempotent.
TSV="/tmp/ff_pdf_manifest.tsv"
LOG="/tmp/ff_pdf_upload.log"
: > "$LOG"
cd "/Users/siraj/Indian Liberals Website"
MAX=8; n=0
while IFS=$'\t' read -r local key mdfile url; do
  (
    if npx wrangler r2 object put "indianliberals-archive/${key}" --file "${local}" --content-type application/pdf --remote >/dev/null 2>>"$LOG"; then
      echo "OK  ${key}" >> "$LOG"
    else
      echo "FAIL ${key}  <- ${local}" >> "$LOG"
    fi
  ) &
  n=$((n+1))
  if (( n % MAX == 0 )); then wait; fi
done < "$TSV"
wait
echo "=== upload done: OK=$(grep -c '^OK ' "$LOG")  FAIL=$(grep -c '^FAIL ' "$LOG") / $(wc -l < "$TSV" | tr -d ' ') ==="
grep '^FAIL' "$LOG" || true
