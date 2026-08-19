# -*- coding: utf-8 -*-
"""Architect stage: decide what will change, in prose, before a single token is spent writing it.

This is the stage the approval gate exists for. The developer approves a *description*, so the
output must contain no code (FR-010b, FR-012) - an intent that smuggled in a class body would
mean the writing tokens were already spent, which is exactly the cost the gate is there to avoid.
`pipeline.ChangeIntent` enforces that invariant; this module's job is to produce one and to
handle the case where the model ignores the instruction.

It binds to the strongest available model, because this is the only stage doing real reasoning -
and it runs once per request, so it is also the cheapest place to spend well. Diagnostics from a
failed build never come back here (FR-020): re-deciding the design would invalidate cache bands
1-3 for no benefit.
"""

from __future__ import annotations

import json
from typing import Final

from cabal.dotnetgen.pipeline import ChangeIntent, IntentContainsCodeError
from cabal.dotnetgen.providers.base import CompletionRequest, Message, Provider

MAX_INTENT_TOKENS: Final[int] = 700

INSTRUCTIONS: Final[str] = (
    "You are the architect stage of a .NET code-generation pipeline.\n"
    "Describe what you would change to satisfy the developer's request. Do not write the change.\n"
    "\n"
    "Reply with a single JSON object and nothing else:\n"
    '  {"summary": "...", "target_files": ["..."], "target_symbols": ["..."], "rationale": "..."}\n'
    "\n"
    "Rules:\n"
    "  - `summary` is prose a developer approves or rejects. One paragraph at most.\n"
    "  - `target_files` are paths you would edit or create, relative to the solution root.\n"
    "  - `target_symbols` are `Namespace.Type.Member` names you would touch.\n"
    "  - `rationale` says why this shape, in prose.\n"
    "  - **Never include C# source, a code fence, a type declaration, or a lambda.**\n"
    "    Naming a type is fine; declaring one is not. The developer is approving a plan, not code."
)

_CORRECTION: Final[str] = (
    "That reply contained code. Re-state the same plan as prose only - no code fence, no type "
    "declaration, no method body. Name symbols, do not define them."
)


class ArchitectError(RuntimeError):
    """Raised when the architect stage cannot produce a usable intent."""


def build_request(
    request_text: str,
    model: str,
    *,
    template_contract: str | None = None,
    structural_map: str | None = None,
) -> CompletionRequest:
    """Assemble the architect call, stable content first so the prefix stays cacheable."""
    messages: list[Message] = [Message(role="system", content=INSTRUCTIONS)]
    if template_contract:
        messages.append(Message(role="system", content=template_contract))
    if structural_map:
        messages.append(Message(role="user", content=structural_map))
    messages.append(Message(role="user", content=request_text))
    return CompletionRequest(
        messages=tuple(messages),
        model=model,
        max_output_tokens=MAX_INTENT_TOKENS,
        temperature=0.0,
    )


def parse(reply: str) -> ChangeIntent:
    """Turn a model reply into an intent. Raises rather than guessing at a malformed one."""
    payload = _extract_object(reply)
    summary = str(payload.get("summary", "")).strip()
    if not summary:
        raise ArchitectError("architect reply has no summary; there is nothing to approve")
    return ChangeIntent(
        summary=summary,
        target_files=tuple(str(f) for f in payload.get("target_files", ())),
        target_symbols=tuple(str(s) for s in payload.get("target_symbols", ())),
        rationale=str(payload.get("rationale", "")).strip(),
    )


def propose(
    request_text: str,
    provider: Provider,
    model: str,
    *,
    template_contract: str | None = None,
    structural_map: str | None = None,
) -> ChangeIntent:
    """Produce an approvable intent, correcting exactly once if the model emits code.

    The single retry is bounded and deliberate. It does not touch `RetryBudget` - that budget
    counts repair attempts against a *verified* failure, and spending it on a model that ignored
    a formatting instruction would let a formatting problem consume the allowance reserved for
    real code defects.
    """
    request = build_request(
        request_text, model, template_contract=template_contract, structural_map=structural_map
    )
    result = provider.complete(request)
    try:
        return parse(result.text)
    except IntentContainsCodeError:
        corrected = CompletionRequest(
            messages=(
                *request.messages,
                Message(role="assistant", content=result.text),
                Message(role="user", content=_CORRECTION),
            ),
            model=request.model,
            max_output_tokens=request.max_output_tokens,
            temperature=request.temperature,
        )
        return parse(provider.complete(corrected).text)


def _extract_object(reply: str) -> dict[str, object]:
    """Read the JSON object out of a reply, tolerating prose or a fence around it.

    A fence around the whole reply is a transport wrapper, not C#, so it is stripped here. The
    no-code invariant still applies with full force - it runs on the parsed `summary` and
    `rationale`, so a fence *inside* a field is caught rather than unwrapped.
    """
    text = reply.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1 : -1 if lines[-1].strip().startswith("```") else None])
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ArchitectError(f"architect reply is not a JSON object: {reply[:200]!r}")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ArchitectError(f"architect reply is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ArchitectError("architect reply must be a JSON object")
    return payload
