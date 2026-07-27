# Running the eval

The agent under test gets exactly what a real agent gets: the archive's tools
and the archive's published contract at `/AGENTS.md`. Nothing about the grading
rubric is disclosed to it. If the contract is clear enough to follow, the score
is high; if it is not, the score is the evidence.

## The instruction given to the agent under test

> You are answering research questions about the Indian liberal tradition using
> the Indian Liberals archive and nothing else.
>
> First read the archive's instructions for agents at
> `https://indianliberals.in/AGENTS.md`. It tells you which content carries
> paragraph-stable citations and which carries only summary-level claims, and
> how to cite each. Follow it exactly.
>
> The archive is reachable two ways, and either is fine:
>
> - MCP at `https://mcp.indianliberals.in/mcp`
> - plain HTTP, one path per tool, e.g.
>   `https://mcp.indianliberals.in/api/search_corpus?query=...`
>
> For each question below: research it, then write the answer you would give a
> reader who intends to cite you. Ground every claim. Do not answer from prior
> knowledge — if the archive does not support a claim, say so.
>
> Return a single JSON object:
>
> ```json
> { "answers": [
>     { "id": "il-0071",
>       "answer": "<your full answer, with citations, as a reader would see it>",
>       "tool_calls": [ { "name": "search_corpus", "args": { "query": "..." } },
>                       { "name": "get_passage",
>                         "args": { "id": "musings:x", "paragraph_ids": ["p-09bb7b"] } } ] } ] }
> ```
>
> `tool_calls` must list every call you actually made, in order.

## What the harness does with that

`grade.py` reads the returned JSON and scores it against `data/eval/pool.json`
and `scripts/eval/corpus.json`. Nothing is inspected by a model.

## Honest limitation

The `strict` score checks that a cited paragraph anchor was actually fetched,
using the `tool_calls` the agent reports. That trace is self-declared. A
cooperative agent reports it accurately; an adversarial one could fabricate it.
The headline `graded` score does not depend on the trace at all — it is
computed from the answer text and the corpus alone — so only `strict` carries
this caveat, and the page at `/eval` says so.

## Batching

Questions are independent. Split the pool across agents however is convenient;
merge the `answers` arrays into one run file before grading. Keep batches at or
below about 10 questions so that no single answer is truncated.

## Run files

`scripts/eval/runs/<label>.json`:

```json
{ "label": "claude-sonnet-5 via MCP, 2026-07-27",
  "answers": [ ... ] }
```

Then:

```
python3 scripts/eval/grade.py scripts/eval/runs/<label>.json --write
```

`--write` publishes `data/eval/results.json`, which is what `/eval` renders.
