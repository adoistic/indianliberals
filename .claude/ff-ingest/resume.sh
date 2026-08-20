#!/bin/zsh
# ff-ingest-resume: OS-cron backstop that resumes the Indian Liberals ingestion
# plan (Freedom First -> drive re-pull -> non-FF backlog) after a usage-limit
# reset. Independent of any live Claude session. Runs 24/7 until the whole
# plan is done — no time-of-day cutoff (removed 2026-07-12 per Adnan: device +
# external drive stay on/mounted, run unattended indefinitely until complete).
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
REPO="/Users/siraj/Indian Liberals Website"
LOG="/tmp/ff-ingest-cron.log"
LOCK="/tmp/ff-ingest.lock"
cd "$REPO" || exit 1
echo "===== $(date '+%F %T %Z') ff-ingest resume fired =====" >> "$LOG"

# PID-based lock: a real run can legitimately stay alive for hours (an entire
# usage window), so a time-staleness check would let a second run start
# concurrently mid-run and corrupt state. Check liveness by PID instead.
if [ -f "$LOCK" ]; then
  OLD_PID=$(cat "$LOCK" 2>/dev/null)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "still running under pid $OLD_PID — skip this tick" >> "$LOG"
    exit 0
  fi
  echo "stale lock (pid $OLD_PID not alive) — clearing" >> "$LOG"
  rm -f "$LOCK"
fi

# Backlog check: if the whole plan is already done, self-remove the cron and stop.
if [ -f "$REPO/.claude/ff-ingest/plan-complete.flag" ]; then
  crontab -l 2>/dev/null | grep -v 'ff-ingest-resume' | crontab -
  echo "plan-complete.flag present — removed cron, not starting a run" >> "$LOG"
  exit 0
fi

echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

# Bounded, unattended run: skip permission prompts so tools can execute headless.
/opt/homebrew/bin/claude -p "$(cat "$REPO/.claude/ff-ingest/resume-prompt.txt")" \
  --dangerously-skip-permissions >> "$LOG" 2>&1
echo "----- exit $? at $(date '+%T') -----" >> "$LOG"
