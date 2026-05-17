"""
LLM dispatcher for the extraction pipeline.

The pipeline runs 100% on Claude Code subagents (Max plan). There is no
OpenRouter mode, no HTTP, no API keys. The orchestrator IS the Claude Code
main session — it dispatches Agents directly via the Agent tool.

This module is a thin helper:

  prepare_request(req)  → packages an extraction request as on-disk files
                          (system + user prompts as .txt, images as .jpg
                          in a per-request directory). The main session
                          dispatches an Agent with those file paths in its
                          prompt.

  parse_response(text)  → takes the JSON text the Agent returned, parses it,
                          returns DispatchResponse with the parsed dict +
                          any error info. The main session captures the
                          subagent's text response and feeds it here.

Token accounting / cost: Claude Code subagents on Max are flat-rate (no
per-call cost from our side). The ledger still records wall_clock_s for
throughput tracking, but `cost_usd` is always None and `input_tokens` /
`output_tokens` are None unless the subagent reports them in its response
body (which we don't require).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
PDF_ROOT = Path("/Volumes/One Touch/Indian Liberals/PDFs-by-publisher")
REQUEST_ROOT = Path("/tmp/llm-extract-requests")


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DispatchRequest:
    """One extraction call's inputs."""
    system_prompt: str
    user_text: str
    images: list[bytes] = field(default_factory=list)  # raw JPEG bytes
    image_page_numbers: list[int] = field(default_factory=list)  # 1-indexed
    model: str = "sonnet"                # "sonnet" | "opus"
    max_output_tokens: int = 4096
    temperature: float = 0.2
    response_format: str = "json"        # "json" | "text"
    # Metadata for the ledger + traceability
    work_slug: str = ""
    job: str = "metadata"                # "byline-sweep" | "metadata" | "summary" | "tiebreak" | "synthesis"
    chunk_idx: int = 0
    prompt_version: str = "v1.0"


@dataclass
class PreparedRequest:
    """On-disk packaging of a DispatchRequest, ready for an Agent dispatch."""
    request_id: str
    request_dir: Path
    system_prompt_path: Path
    user_text_path: Path
    image_paths: list[Path]
    suggested_agent_prompt: str          # what to pass to Agent.prompt
    suggested_model: str                 # "sonnet" | "opus"
    job: str
    work_slug: str
    chunk_idx: int


@dataclass
class DispatchResponse:
    """Parsed result of a single dispatch."""
    ok: bool
    parsed_json: dict | None
    raw_text: str
    input_tokens: int | None             # subagent rarely reports these; usually None
    output_tokens: int | None
    cost_usd: float | None               # always None for subagent mode (Max-flat)
    wall_clock_s: float
    error: str | None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def prepare_request(req: DispatchRequest) -> PreparedRequest:
    """
    Package a DispatchRequest into on-disk files so the main session can
    dispatch an Agent with `Read` tool access to the prompts + images.

    Returns the file paths and a suggested Agent prompt that asks the
    subagent to read the prompt files + images and return JSON.
    """
    request_id = uuid.uuid4().hex[:12]
    request_dir = REQUEST_ROOT / req.job / f"{req.work_slug or 'unknown'}-chunk{req.chunk_idx}-{request_id}"
    request_dir.mkdir(parents=True, exist_ok=True)

    # Write system + user prompts to text files
    system_path = request_dir / "system.txt"
    system_path.write_text(req.system_prompt, encoding="utf-8")
    user_path = request_dir / "user.txt"
    user_path.write_text(req.user_text, encoding="utf-8")

    # Write images as page-NN.jpg in chunk order
    image_paths: list[Path] = []
    for idx, (img_bytes, page_num) in enumerate(
        zip(req.images, req.image_page_numbers or list(range(1, len(req.images) + 1))),
        start=1,
    ):
        img_path = request_dir / f"page-{page_num:03d}.jpg"
        img_path.write_bytes(img_bytes)
        image_paths.append(img_path)

    # Build the Agent prompt — instructions to the subagent on what to read + how to respond
    suggested_prompt = _build_agent_prompt(
        system_path=system_path,
        user_path=user_path,
        image_paths=image_paths,
        response_format=req.response_format,
    )

    return PreparedRequest(
        request_id=request_id,
        request_dir=request_dir,
        system_prompt_path=system_path,
        user_text_path=user_path,
        image_paths=image_paths,
        suggested_agent_prompt=suggested_prompt,
        suggested_model=req.model,
        job=req.job,
        work_slug=req.work_slug,
        chunk_idx=req.chunk_idx,
    )


def parse_response(
    raw_text: str,
    *,
    response_format: str = "json",
    wall_clock_s: float = 0.0,
) -> DispatchResponse:
    """
    Take the text the Agent returned, parse it, return a DispatchResponse.

    For JSON responses, strips common markdown-fence wrappers ('```json ... ```')
    before parsing.
    """
    raw_text = raw_text.strip()

    if response_format == "text":
        return DispatchResponse(
            ok=True,
            parsed_json=None,
            raw_text=raw_text,
            input_tokens=None,
            output_tokens=None,
            cost_usd=None,
            wall_clock_s=wall_clock_s,
            error=None,
        )

    # JSON mode: strip markdown fences if present
    cleaned = _strip_markdown_fence(raw_text)

    parsed: dict | None = None
    error: str | None = None
    try:
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            error = f"Expected JSON object, got {type(parsed).__name__}"
            parsed = None
    except json.JSONDecodeError as e:
        error = f"JSON parse failed: {e}"

    return DispatchResponse(
        ok=error is None,
        parsed_json=parsed,
        raw_text=raw_text,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,  # Max plan, no per-call cost
        wall_clock_s=wall_clock_s,
        error=error,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_agent_prompt(
    *,
    system_path: Path,
    user_path: Path,
    image_paths: list[Path],
    response_format: str,
) -> str:
    """Build the prompt the main session passes to the Agent tool."""
    image_list = "\n".join(f"- {p}" for p in image_paths)
    response_instruction = (
        "Return JSON only. No preamble. No markdown fence. No trailing prose."
        if response_format == "json"
        else "Return plain text only. No preamble."
    )
    return (
        f"You are an LLM extraction subagent for the Indian Liberals archive.\n\n"
        f"1. Read the SYSTEM prompt from: {system_path}\n"
        f"2. Read the USER prompt from: {user_path}\n"
        f"3. Read each of the following {len(image_paths)} page images (these are the rendered PDF pages you'll analyse):\n"
        f"{image_list}\n\n"
        f"Then follow the SYSTEM prompt's instructions, applied to the images, "
        f"per the USER prompt. {response_instruction}\n\n"
        f"Do not add commentary about what you're doing — emit the final output only."
    )


def _strip_markdown_fence(text: str) -> str:
    """Strip a leading ```json or ``` fence and trailing ``` if present."""
    text = text.strip()
    if text.startswith("```"):
        # Drop first line (```json or ```)
        nl = text.find("\n")
        if nl > -1:
            text = text[nl + 1 :]
        # Drop trailing ```
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    return text


# ---------------------------------------------------------------------------
# CLI for local smoke-testing
# ---------------------------------------------------------------------------


def _cli_smoke_test() -> None:
    """
    Local smoke test: package a fake request, print the prepared paths +
    suggested agent prompt, then test parse_response on a fenced JSON sample.
    """
    print("=== prepare_request ===")
    req = DispatchRequest(
        system_prompt="# SYSTEM\nYou extract metadata.",
        user_text="# USER\nPDF: foo.pdf\nPages: [1, 2]",
        images=[b"\xff\xd8\xff\xe0fakejpeg1", b"\xff\xd8\xff\xe0fakejpeg2"],
        image_page_numbers=[1, 2],
        model="sonnet",
        work_slug="test-pamphlet",
        job="metadata",
        chunk_idx=0,
        prompt_version="v1.0-smoke",
    )
    prepared = prepare_request(req)
    print(f"  request_id:   {prepared.request_id}")
    print(f"  request_dir:  {prepared.request_dir}")
    print(f"  system_path:  {prepared.system_prompt_path}")
    print(f"  user_path:    {prepared.user_text_path}")
    print(f"  image_paths:  {[p.name for p in prepared.image_paths]}")
    print(f"  suggested_model: {prepared.suggested_model}")
    print()
    print("=== suggested_agent_prompt ===")
    print(prepared.suggested_agent_prompt)
    print()

    print("=== parse_response (fenced JSON) ===")
    fenced = '```json\n{"title": "Test", "year": 1965}\n```'
    resp = parse_response(fenced)
    print(f"  ok:           {resp.ok}")
    print(f"  parsed_json:  {resp.parsed_json}")
    print(f"  error:        {resp.error}")
    print()

    print("=== parse_response (bare JSON, JSON error) ===")
    bad = '{"title": "Test", "year": 1965'
    resp = parse_response(bad)
    print(f"  ok:           {resp.ok}")
    print(f"  error:        {resp.error}")


if __name__ == "__main__":
    _cli_smoke_test()
