# Session handoff — 2026-08-20

Paste the block below into a new session. Everything above the line is context
for a human; the prompt itself starts at "## PROMPT".

---

## PROMPT

I'm continuing work on the Swatantra Party papers ingest for the Indian
Liberals Website. Previous session ran long; here's the state.

### Repo and machine
- Repo: `/Users/siraj/Indian Liberals Website`, branch `swatantra-papers-ingest`
- Two commits, **unpushed**: `d8e3307a`, `d6206a2d`
- Corpus PDFs: Google Drive mount, and also public on R2 at
  `https://archive.indianliberals.in/swatantra-party-papers/<slug>.pdf`
- Python for this work: `.venv-extract/bin/python3` (system python3 lacks deps)

### 1. Extraction — running in the cloud
A RunPod CPU pod is extracting the remaining corpus with `gpt-5-6-luna` via
kie.ai.

- Pod `zp22lbsus1eaak`, `ssh root@213.173.111.107 -p 25296` (key already
  authorised), $0.07/hr
- Running: `/root/swatantra-bundle/run.sh`, log at `/root/ingest.log`
- Last seen: 3,856 of 5,177 works, ~840/hr, ~$10.74 spent
- **Terminate the pod when extraction finishes** — it bills whether or not it
  is working. Use the runpod MCP (`delete-pod`) or the dashboard.

Pull results down (do this before terminating):
```
cd "/Users/siraj/Indian Liberals Website"
rsync -az -e "ssh -o StrictHostKeyChecking=no -p 25296" \
  root@213.173.111.107:/root/swatantra-bundle/data/bake-off-output/ \
  data/swatantra-papers/cloud-results/
```

Local status check:
```
.venv-extract/bin/python3 scripts/swatantra/kie-ingest.py --status \
  --skip-file data/swatantra-papers/already-done.json
```

### 2. Decisions already made — please don't re-litigate these
All were settled by measurement, written up in `docs/kie-ai-api.md`:

- **all-Luna, one metadata pass + summary.** Terra costs 11x for +1.8 points;
  a Luna/Terra split has only 33% bias-detector recall because both are OpenAI
  models and make correlated errors.
- **`metadata.b` dropped.** The Opus tiebreak it feeds has never once been
  dispatched (zero tiebreak records across 1,177 works), and the disagreement
  flag fires on 45% of works — half of those on `publisher_verbatim` alone.
- **Rights are cleared.** CCS granted permission; the corpus is going public.
  Not a blocker for merging to main or for external inference providers.
- Quality: Luna is ~77% field accuracy, ~80% with the filename `work_type` fix.
  Below Sonnet, accepted deliberately for a 25x cost saving.

### 3. What still needs doing
1. **Finish/verify extraction**, pull results, terminate the pod.
2. **~240 `UNPARSEABLE` summary failures** (~7%). All on the `summary` job, no
   API errors — Luna returns non-JSON. Re-running the ingest retries only the
   gaps (it skips completed jobs). Better: patch `kie-ingest.py` to save the
   failing text to `data/swatantra-papers/kie-unparseable/` before diagnosing.
   I started that edit and reverted it; redo it deliberately.
3. **Merge into content entries**: `scripts/swatantra/merge-extraction.py`.
   It now applies the deterministic filename `work_type` fix
   (`scripts/swatantra/filename_worktype.py`) — entries where it fired carry
   `work_type_source: filename`. Run on a slice and eyeball those first.
4. **`scripts/analysis/tfidf.py` against the 9x corpus** — untested at this
   scale, flagged as a scaling risk.
5. **Push the branch**, then decide on merging to main (Pages deploys from
   main).
6. A **Claude sub-agent review pass** over extracted records was planned —
   particularly `work_type` where the filename gives no cue, and
   `publisher_verbatim` truncations.

### 4. Security incident — separate track, mostly done
This machine was compromised 2026-06-29 (ClickFix → blockchain-C2 loader →
XMRig miner), discovered and remediated 2026-08-20.

- Full package: `~/Downloads/security-incident-2026-08-20/` and `.zip`
  (report + addendum in docx/pdf/md, plus evidence)
- **Confirmed:** `~/.passphrase` authenticates as the live macOS login
  password, captured 33s after infection, held 52 days.
- **Outstanding and not done: credential rotation.** macOS password,
  Cloudflare/R2, GitHub, Google, `.env` API keys, Anthropic. The kie key in
  `.env` was live on a compromised machine the whole time.
- Don't re-investigate unless asked — it's written up and going to an expert.

### 5. Gotchas that cost time last session
- kie has **two** API surfaces: Claude at `/claude/v1/messages` (Anthropic
  shape) and OpenAI at `/codex/v1/responses` (Responses shape, **dashed**
  model ids). `/api/v1/chat/completions` is a decoy. Auth is Bearer; `x-api-key`
  401s. The Claude route never accepted a single image request.
- Omitting `instructions` on the codex route injects 12k chars of Codex
  coding-agent prompt. Always pass it.
- Cloudflare 403s the default `Python-urllib` agent — send a real User-Agent.
- macOS `tar` adds AppleDouble `._*` files; use `COPYFILE_DISABLE=1`.
- The pod has python3.8 AND python3.11; use 3.11 and set `PYTHONUTF8=1`.
- Always pass `LLM_EXTRACT_PIN_THINKERS_FILE` — without it the authority
  subset drops 28 pinned ids and `thinker_id: null` becomes *correct*, which
  reads as a model failure but is a harness bug.

Start by checking extraction status and telling me where things stand.
