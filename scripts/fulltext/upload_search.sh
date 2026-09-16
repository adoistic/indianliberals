#!/bin/zsh
# Upload a rebuilt Pagefind bundle to R2 under search/.
#
# ORDER IS THE WHOLE POINT. The /search/ page was degraded for about thirty
# minutes because a previous ad-hoc version of this uploaded the bundle in
# directory order: `pkill` killed the xargs doing the shard uploads, the parent
# script carried on to the next line, and the ENTRYPOINTS went up while 1,436
# fragment and index shards were still missing. A fresh entrypoint pointing at
# absent shards is worse than a stale entrypoint pointing at the old bundle,
# because the old bundle still works.
#
# So: content-hashed shards first, then a check, and only then the entrypoints
# that name them. If a single shard fails, the entrypoints are not touched and
# the live index keeps serving the previous build.
#
# Resumable: every successful key is appended to uploaded_search.tsv and skipped
# on a re-run. Delete that file to force a full re-upload.
#
# Parallelism is 4 on purpose. A 28-way run drew 1,064 "429 Too Many Requests"
# from the R2 API, which caps at roughly 4 requests a second.
#
# Usage: scripts/fulltext/upload_search.sh <bundle-dir>
set -e
REPO="/Users/siraj/Indian Liberals Website"
WR="${WRANGLER_BIN:-$REPO/apps/site/node_modules/.bin/wrangler}"  # npx is broken here (ENOTEMPTY)
CWD="$REPO/apps/site"
BUCKET="indianliberals-archive"
LOG="${UPLOAD_LOG:-$PWD/uploaded_search.tsv}"

ct_for() {
  case "$1" in
    *.js)          print -r -- "application/javascript" ;;
    *.json)        print -r -- "application/json" ;;
    *.css)         print -r -- "text/css" ;;
    *.wasm)        print -r -- "application/wasm" ;;
    *.gz)          print -r -- "application/gzip" ;;
    *)             print -r -- "application/octet-stream" ;;
  esac
}

# Re-entrant worker: xargs cannot call a shell function, so it calls this
# script back with --one. That is also what keeps the -P 4 fan-out honest.
if [[ "$1" == "--one" ]]; then
  file="$2"; key="search/${2#${BUNDLE_ROOT%/}/}"
  if [[ -f "$LOG" ]] && cut -f1 "$LOG" | grep -qxF "$key"; then exit 0; fi
  ct=$(ct_for "$file")
  for a in 1 2 3 4 5; do
    if "$WR" r2 object put "$BUCKET/$key" --file "$file" --content-type "$ct" --remote \
         >/dev/null 2>&1; then
      printf '%s\t%s\n' "$key" "$(stat -f%z "$file")" >> "$LOG"
      exit 0
    fi
    sleep $((a * a * 2))          # exponential backoff; R2 rate-limits hard
  done
  printf 'FAILED\t%s\n' "$key" >&2
  exit 1
fi

SELF="${0:A}"
BUNDLE="${1:?usage: upload_search.sh <bundle-dir>}"
BUNDLE="${BUNDLE%/}"
touch "$LOG"
cd "$CWD"

# An entrypoint is a file a browser asks for BY NAME, so it must never point at
# shards that are not there yet. Everything under fragment/ and index/ is
# content-hashed and safe to upload in any order.
shards=(); entries=()
for f in $BUNDLE/**/*(.); do
  case "${f#$BUNDLE/}" in
    # filter/ is content-hashed payload too, and memory is explicit that
    # fragment/, index/ AND filter/ all go up before the entrypoints. The
    # first version of this list omitted filter/, which would have shipped
    # 21 filter files in phase 2 alongside pagefind-entry.json.
    fragment/*|index/*|filter/*) shards+=("$f") ;;
    *)                  entries+=("$f") ;;
  esac
done
print -r -- "bundle: ${#shards} content-hashed shards, ${#entries} entrypoints"
(( ${#shards} )) || { print -r -- "no shards found - wrong bundle dir?" >&2; exit 4; }

# The worker derives its own key from BUNDLE_ROOT, so nothing has to be quoted
# into an xargs command line. An earlier version tried and produced
# "xargs: command line cannot be assembled, too long" on a six-file bundle.
run_phase() {   # run_phase <label> <files...>
  local label="$1"; shift
  print -r -- "--- $label ($# files) ---"
  local rc=0
  export UPLOAD_LOG="$LOG" BUNDLE_ROOT="$BUNDLE" WRANGLER_BIN="$WR"
  printf '%s\n' "$@" | xargs -P 4 -I{} "$SELF" --one {} || rc=$?
  return $rc
}

fail=0
run_phase "phase 1: shards" "${shards[@]}" || fail=1
print -r -- "phase 1: $(wc -l < "$LOG" | tr -d ' ') key(s) logged in $LOG"
if (( fail )); then
  print -r -- "REFUSING to upload entrypoints: at least one shard failed." >&2
  print -r -- "The live index keeps serving the previous build. Re-run to resume." >&2
  exit 2
fi

run_phase "phase 2: entrypoints" "${entries[@]}" || {
  print -r -- "entrypoint upload incomplete - re-run to finish" >&2; exit 3; }
print -r -- "done. search/ entrypoints are cached 300s, so the rebuild is live within 5 minutes."
