# kie.ai API — operational notes

Discounted third-party access to Claude, GPT, Gemini and Grok. Written against
live probing on 2026-08-18 for the Swatantra papers extraction run; every
number here was measured, not taken from marketing copy.

The single most important fact: **kie exposes two unrelated LLM surfaces.**
They have different base paths, different request shapes, different model-id
spellings, and — as of this writing — very different reliability. Picking the
wrong one produces 404s that look like auth problems.

| | Anthropic models | OpenAI models |
|---|---|---|
| Endpoint | `https://api.kie.ai/claude/v1/messages` | `https://api.kie.ai/codex/v1/responses` |
| Wire format | Anthropic **Messages** | OpenAI **Responses** (*not* chat/completions) |
| Model id | dotted — `claude-sonnet-5` | **dashed** — `gpt-5-6-luna` |
| Images | `image` block, base64 in `source.data` | `input_image`, `data:` URI in `image_url` |
| System prompt | `system` | `instructions` |
| Reasoning control | `thinking` / effort suffix on served model | `reasoning.effort` |

`https://api.kie.ai/api/v1/chat/completions` exists but answers
`{"code":404,"msg":"This feature is currently not supported"}` for every chat
model tried. It is not the OpenAI route. Don't use it.

## Authentication

`Authorization: Bearer <key>` on both surfaces. **`x-api-key` returns 401** even
on the Anthropic-shaped endpoint — this is the most likely first mistake when
porting existing Anthropic code, because the shape is otherwise identical.

Key lives in `.env` as `KIE_API_KEY` (gitignored).

Balance check — the only account endpoint found:

```bash
curl -H "Authorization: Bearer $KIE_API_KEY" https://api.kie.ai/api/v1/chat/credit
# {"code":200,"msg":"success","data":9906.48}
```

Credits convert at **200 credits = $1**.

## OpenAI models — the working path

```bash
curl -X POST https://api.kie.ai/codex/v1/responses \
  -H "Authorization: Bearer $KIE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5-6-luna",
    "stream": false,
    "instructions": "<your system prompt>",
    "input": [{"role": "user", "content": [
      {"type": "input_image", "image_url": "data:image/jpeg;base64,<...>"},
      {"type": "input_text",  "text": "<your user prompt>"}
    ]}],
    "reasoning": {"effort": "low"}
  }'
```

Model ids: `gpt-5-6-luna`, `gpt-5-6-terra`, `gpt-5-6-sol`, `gpt-5-5`, `gpt-5-4`,
`gpt-5-2`, and the codex variants. **Dashes, not dots** — `gpt-5.6-luna` is
rejected. Confusingly the *response* echoes `"model": "gpt-5.6-luna"` in dotted
form; that is display only, don't feed it back.

`reasoning.effort` accepts `low` | `medium` | `high` | `xhigh`, default `low`.

`tools` supports web search **or** function calling, never both in one request.

### `instructions` defaults to a Codex agent prompt — override it

If you omit `instructions`, kie injects **12,217 characters (~3,050 tokens)** of
Claude-Code-style Codex system prompt: *"You are Codex, a coding agent based on
GPT-5. You and the user share the same workspace…"* — personality section,
update cadence rules, the lot. For a structured-extraction task that is
contamination, and it is invisible unless you read the echoed `instructions`
field on the response.

Passing your own `instructions` **replaces it completely** (verified: 53-char
override came back as 53 chars, no Codex text). Always pass it explicitly.

The Anthropic surface has the same problem and no clean fix found: a request
with no `system` and a 12-token user message still reported
`cache_read_input_tokens: 24842`, i.e. ~25k tokens of something we did not
send. Budget for it on that route.

### Images

`input_image` takes a `data:` URI, so local page scans work without uploading
anywhere first:

```python
{"type": "input_image",
 "image_url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}
```

A 227 KB page JPEG inside a 372 KB request body was accepted and read
correctly. Put the image **before** the text block, as with Anthropic.

### Response shape

Text is nested two levels deep — not `choices[0].message.content`:

```python
text = "".join(c.get("text", "")
               for o in payload["output"] if o.get("type") == "message"
               for c in o.get("content", []))
```

Useful top-level fields: `status` (`completed`), `usage`, `credits_consumed`,
and `instructions` (echoed — check it to confirm your override landed).

## Measured on this corpus

8 baked one-page Swatantra letters replayed through `gpt-5-6-luna` at
`effort: low`, with the real extraction prompt and one page image each:

| | value |
|---|---|
| success rate | 8/8, all first attempt |
| mean wall clock | 21.4 s |
| mean input tokens | 18,954 |
| mean output tokens | 867 |
| credits per document | 0.26 (**$0.0013**) |
| cache tokens | 0 — no prompt caching observed on this route |

The measured 18,954 input tokens per job closely matches the 17,100 estimated
from Anthropic's image tokenisation, so cost projections built on that estimate
hold to within ~10%.

Note **no caching on the codex route** (`cached_tokens: 0`, `cache_write_tokens:
0`). The Anthropic route does report cache reads. Any cost model that assumes
the ~85% cacheable prefix will be wrong here — but at $0.0013/doc uncached it
hardly matters.

## Reliability

The failure rate is real and it is **not uniform across models or time**:

- `claude-sonnet-5` succeeded instantly, then later returned HTTP 500 on every
  request for an extended period — including a request byte-identical to one
  that had just succeeded. A five-cell diagnostic varying payload size and
  image presence failed in all five cells, so during an outage it is the
  endpoint, not the request.
- `claude-haiku-4-5` returned 500 on 3/3 attempts while `claude-sonnet-5` was
  working.
- `gpt-5-6-luna` on the codex route: 16/16 first-attempt successes across two
  runs, no retries needed.

500s carry `{"type":"error","error":{"type":"api_error","message":"Server
exception, please try again later"}}`. Retry with backoff, but treat a run of
them as an outage rather than a transient — five attempts over 155 s did not
recover in observed cases. Credits are not consumed on a failed request.

## Pricing (USD per 1M tokens, checked 2026-08-18)

| Model | In | Out | Official | Discount |
|---|---|---|---|---|
| `claude-opus-5` | $2.00 | $10.00 | $5/$25 | −60% |
| `claude-sonnet-5` | $0.85 | $4.275 | $2/$10 intro | −57% |
| `claude-haiku-4-5` | $0.275 | $1.425 | $1/$5 | −72% |
| `gpt-5-6-sol` | $1.40 | $8.40 | $5/$30 | −72% |
| `gpt-5-6-terra` | $0.56 | $3.36 | $2/$12 | −72% |
| `gpt-5-6-luna` | $0.056 | $0.336 | $0.20/$1.20 | −72% |
| Gemini 3.7 Flash | $0.225 | $1.125 | $0.75/$3.75 | −70% |

Anthropic-route caching is billed at the real multipliers (write 1.25× / 5 min,
2.0× / 1 hr, read 0.10×).

## Using it from this repo

`scripts/swatantra/kie-replay.py` drives both surfaces behind one `--route`
flag (`anthropic` | `codex`) and normalises the two response shapes. It only
touches works that already have a baked record, so every call is scoreable.
`scripts/swatantra/kie-compare.py` scores the results against the baseline.

Two harness requirements, both learned the hard way:

1. Pass `LLM_EXTRACT_PIN_THINKERS_FILE`. Without it the authority subset omits
   the 28 pinned ids, and the binary resolution rule then makes
   `thinker_id: null` the *correct* output — which reads as a model-quality
   failure when it is a harness misconfiguration.
2. Keep prompt changes for weaker models in
   `prompts/metadata-weak-model-addendum.md` and append them at dispatch.
   Editing the shared `metadata.a.md` would make the already-baked corpus
   incomparable with everything extracted afterwards.

---

# Quality trial: are the cheap models good enough for this corpus?

Run 2026-08-18/20. 40 works, stratified across 1–20 pages and 8 document types
(7 telegrams pulled in deliberately — 2.2% of the corpus, but where failures
concentrate). Three passes: `metadata.a` on gpt-5-6-luna, `metadata.b` and
`summary` on gpt-5-6-terra. 120/120 requests succeeded. Cost $1.55.

## Verdict: no. Do not run this corpus on Luna, and do not use a Luna/Terra split.

**The split does not catch the cheap model's errors.** The pipeline's quality
mechanism is a/b disagreement escalating to a tiebreak, so the split was meant
to let a second model flag the first one's systematic bias:

| | |
|---|---|
| Luna errors that escalated (caught) | 17 |
| Luna errors that shipped silently | **34** |
| bias-detector recall | **33%** |
| silent error rate, all fields | **15.4%** |
| escalation rate, luna/terra | 48% |
| escalation rate, sonnet a/b | 35% |

It is the worst of both: *more* tiebreak calls than the Sonnet baseline (48% vs
35%, so higher cost) while still shipping 15% of fields wrong.

**Why it fails: the two models' errors are correlated.** They are both OpenAI
models and they make the *same* mistakes, so disagreement never fires. Both
collapse `minutes`/`essay`/`press_note`/`circular` into `occasional_paper`;
both drop street addresses from publisher lines; both misread the same
newsletter telephone number identically (`251434` → `251424`). A split only
detects bias when the two arms fail independently.

**The quality gap is much larger than the one-page-letter sample suggested.**

| sample | luna `work_type` accuracy |
|---|---|
| 48 one-page letters | 87.5% |
| 40 stratified works | **47.5%** |

The earlier 8-point gap was an artefact of testing only the easiest documents.

**Independent corroboration.** Using Sonnet as ground truth is circular, so the
22 works whose *filename* names the document form (typed by the archivist,
model-independent) were scored separately:

| | matches filename |
|---|---|
| Sonnet | **82%** |
| Terra | 73% |
| Luna | 64% |

Sonnet's four "misses" are mostly documents filed as `Letter_to_X` that are
actually telegrams — it read the form off the page where the cataloguer went
with a generic name. Its true accuracy is therefore higher than 82%.

**The specific pathology.** `occasional_paper` is Luna's sink for anything that
is not obviously a letter or a periodical: minutes of the National Executive,
numbered party circulars, press statements and newspaper essays all land there.
`work_type` drives the eyebrow label, the browse facets and the filtering on
the site, so this is structural degradation of the archive, not a rounding
error.

## What to use instead

The Max-plan `claude -p` route remains the best option for this corpus: $0
marginal cost, and it is the exact configuration that produced the known-good
baseline. Its only cost is wall-clock and rate limits.

If throughput matters more than money, buy a strong model rather than a split —
Opus 5 (~$724) or Sonnet 5 (~$308) over the remaining corpus. A cross-*family*
split (Luna + Sonnet/Gemini) might decorrelate the errors, but with Luna's
`work_type` at 47.5% more than half the corpus would escalate to arbitration,
which erases the cost advantage that motivated the cheap model in the first
place.
