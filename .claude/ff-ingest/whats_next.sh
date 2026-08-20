#!/bin/zsh
# Single source of truth for "what should I do next" across the two active
# initiatives: (1) Freedom First ingestion, (2) the other-works R2 migration.
# Run this any time to know exactly what's left and what to do next.
cd "/Users/siraj/Indian Liberals Website"

echo "=================================================================="
echo "1. FREEDOM FIRST INGESTION"
echo "=================================================================="
ls "/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/freedom-first/"FF*.pdf 2>/dev/null | sed 's#.*/##;s#\.pdf$##' | sort -u > /tmp/od.txt
ls apps/site/src/content/primary-works/ff*.md 2>/dev/null | sed 's#.*/ff#FF#;s#\.md$##' | tr a-z A-Z | sort -u > /tmp/dn.txt
FF_BACKLOG=$(comm -23 /tmp/od.txt /tmp/dn.txt)
FF_BACKLOG_COUNT=$(echo -n "$FF_BACKLOG" | grep -c . || echo 0)
echo "downloaded: $(wc -l < /tmp/od.txt | tr -d ' ')  ingested: $(wc -l < /tmp/dn.txt | tr -d ' ')  remaining: $FF_BACKLOG_COUNT"
if [ "$FF_BACKLOG_COUNT" -gt 0 ]; then
  NEXT6=$(echo "$FF_BACKLOG" | head -6 | tr '\n' ' ')
  echo ">>> ACTION: FF not done. Next batch: $NEXT6"
  echo ">>> Run: zsh \".claude/ff-ingest/ff_prep.sh\" /tmp/ff_batchNN.tsv $NEXT6"
else
  echo ">>> FF backlog is EMPTY. All downloaded FF issues are ingested."
fi

echo ""
echo "=================================================================="
echo "2. NON-FF WORKS -> R2 MIGRATION"
echo "=================================================================="
if [ ! -f /tmp/other_works_manifest.tsv ]; then
  echo ">>> Manifest not yet generated. Run:"
  echo ">>> .venv-extract/bin/python3 .claude/ff-ingest/migrate_other_works.py"
else
  TOTAL=$(wc -l < /tmp/other_works_manifest.tsv | tr -d ' ')
  DONE=$(grep -c '^OK ' /tmp/other_works_upload.log 2>/dev/null || echo 0)
  FAIL=$(grep -c '^FAIL ' /tmp/other_works_upload.log 2>/dev/null || echo 0)
  echo "manifest total: $TOTAL   uploaded OK: $DONE   FAILED: $FAIL"
  if [ "$DONE" -lt "$TOTAL" ]; then
    echo ">>> ACTION: uploads incomplete. Run (safe to re-run, skips nothing but cheap):"
    echo ">>> zsh \".claude/ff-ingest/migrate_other_works_upload.sh\""
  else
    # check if pdf_url has actually been swapped yet
    SWAPPED=$(grep -rl 'pdf_url:.*pub-f1430c20cc1c400da542453c56d614c8\.r2\.dev' apps/site/src/content/primary-works/*.md 2>/dev/null | grep -vc '/ff[0-9]')
    echo "non-FF entries with pdf_url already swapped to R2: $SWAPPED / $TOTAL"
    if [ "$SWAPPED" -lt "$TOTAL" ]; then
      echo ">>> ACTION: uploads done, but pdf_url not yet swapped. Run:"
      echo ">>> .venv-extract/bin/python3 .claude/ff-ingest/migrate_other_works.py --set-urls"
      echo ">>> then: astro sync, then commit+push (in batches — see below)"
    else
      echo ">>> Non-FF migration is FULLY DONE (uploaded + pdf_url swapped)."
      UNCOMMITTED=$(git status --short apps/site/src/content/primary-works/*.md 2>/dev/null | grep -vc 'ff[0-9]\{3\}\.md')
      echo "uncommitted non-FF .md changes: $UNCOMMITTED"
      if [ "$UNCOMMITTED" -gt 0 ]; then
        echo ">>> ACTION: commit+push remaining. Suggest batching ~150-200 files per commit."
      fi
    fi
  fi
fi

echo ""
echo "=================================================================="
if [ "$FF_BACKLOG_COUNT" -eq 0 ] && [ -f /tmp/other_works_manifest.tsv ]; then
  DONE=$(grep -c '^OK ' /tmp/other_works_upload.log 2>/dev/null || echo 0)
  TOTAL=$(wc -l < /tmp/other_works_manifest.tsv | tr -d ' ')
  if [ "$DONE" -ge "$TOTAL" ]; then
    echo "*** BOTH INITIATIVES COMPLETE ***"
  fi
fi
