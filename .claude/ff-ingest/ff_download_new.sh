#!/bin/zsh
# Downloads any Freedom First issue PDFs present in the shared Google Drive
# folder but missing locally, into PDFs-by-publisher/freedom-first/.
# Safe to run repeatedly / speculatively: only copies files not already
# present locally (rclone copy is size+modtime idempotent by default).
#
# Usage: zsh ff_download_new.sh
#
# Prereq: the Drive folder (root_folder_id in ~/.config/rclone/rclone.conf,
# currently 1tSZGFCbbolc1Nu_v_lnBIsbpCARcKn8H) must be shared with the
# account rclone is authenticated as. Until then this exits early with a
# clear message rather than silently no-op'ing.

set -e
LOCAL_DIR="/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/freedom-first"
REMOTE="gdrive:"
ROOT_ID="1tSZgFCbbolc1Nu_v_lnBIsbpCARcKn8H"  # NOTE: lowercase 'g' (5th char) — a case-typo here caused hours of false "access denied" diagnosis

echo "=== checking Drive access ==="
if ! rclone lsf "$REMOTE" --drive-root-folder-id "$ROOT_ID" --max-depth 1 >/tmp/ff_remote_listing.txt 2>/tmp/ff_remote_err.txt; then
  echo "BLOCKED: Drive folder still inaccessible. Error:"
  cat /tmp/ff_remote_err.txt
  exit 1
fi

echo "=== remote listing ok, $(wc -l < /tmp/ff_remote_listing.txt | tr -d ' ') entries found ==="
echo "=== local FF PDF count before: $(ls "$LOCAL_DIR"/FF*.pdf 2>/dev/null | wc -l | tr -d ' ') ==="

echo "=== syncing missing FF*.pdf files (existing local files left untouched) ==="
echo "=== NOTE: --max-depth 1 excludes the 'compressed/' subfolder (per Adnan: skip it entirely) ==="
rclone copy "$REMOTE" "$LOCAL_DIR" \
  --drive-root-folder-id "$ROOT_ID" \
  --max-depth 1 \
  --include "FF*.pdf" \
  --ignore-existing \
  --progress \
  --transfers 8 --checkers 8

NEW_COUNT=$(ls "$LOCAL_DIR"/FF*.pdf 2>/dev/null | wc -l | tr -d ' ')
echo "=== local FF PDF count after: $NEW_COUNT ==="
echo "=== done. Recompute the un-ingested backlog with comm -23 as usual, then continue the batch-ingest loop. ==="
