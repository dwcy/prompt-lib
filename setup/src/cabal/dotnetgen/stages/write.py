# -*- coding: utf-8 -*-
"""Write stage: turn an approved intent into edit operations, emitting only what changes.

This is the mechanical stage, and it is where output tokens - the expensive, serial ones at
roughly 5x input price - are actually spent. Two rules do the cost work:

* **emit edits, never files.** An operation carries the new content for one anchored region.
  Re-emitting an unchanged member is the single most common waste in naive pipelines, and
  `edits.model` rejects it as a no-op rather than trusting the instruction to be followed.
* **one type per file** (`global/rules/csharp.md`), so an edit's blast radius stays small enough
  that a failed apply costs one retry rather than a whole file.

Because it is mechanical, it is the stage that can bind to a cheap or locally-hosted model
(SC-008) - and it is where build diagnostics are routed back on repair, never to the architect
(FR-020), so a repair never re-decides the design or invalidates cache bands 1-3.
"""

from __future__ import annotations

import json
from typing import Final

from cabal.dotnetgen.edits.model import EditOperation, EditOperationError, parse_operation
from cabal.dotnetgen.pipeline import ChangeIntent
from cabal.dotnetgen.providers.base import CompletionRequest, Message, Provider

MAX_WRITE_TOKENS: Final[int] = 4000

INSTRUCTIONS: Final[str] = (
    "You are the writing stage of a .NET code-generation pipeline. An architect has already "
    "decided what changes; you produce the edits, and you do not revisit the design.\n"
    "\n"
    'Reply with a single JSON object: {"operations": [ ... ]} and nothing else.\n'
    "\n"
    "Each operation is one anchored change to one file:\n"
    '  {"file": "src/Api/Features/Orders/CancelOrder.cs",\n'
    '   "anchor_kind": "symbol" | "text",\n'
    '   "symbol": "Namespace.Type.Member(signature)",   // when anchor_kind is symbol\n'
    '   "search": "exact existing text",                // when anchor_kind is text\n'
    '   "disposition": "replace" | "insert-into-type" | "delete" | "create-file",\n'
    '   "content": "the new C# source for this region",\n'
    '   "reason": "why this edit"}\n'
    "\n"
    "Rules, all of which are enforced and will reject your reply:\n"
    "  - Never include a line number. Anchors are content, not position.\n"
    "  - Never write a placeholder such as `// ... rest unchanged` or `// existing code here`. "
    "Emit the complete content for the region you are changing.\n"
    "  - Never re-emit a region you are not changing. Fewer, smaller operations are better.\n"
    "  - `delete` carries no content. `create-file` carries the whole new file.\n"
    '  - For `create-file`, set `anchor_kind` to "symbol" and `symbol` to the fully-qualified '
    "name of the type the new file declares. A new file has nothing to anchor against, but the "
    "contract still requires an anchor, and the declared type is the honest one.\n"
    "  - One type per file. File-scoped namespaces, `sealed` by default, `record` for DTOs.\n"
    "  - Commands mutate state and Queries return data; never mix them in one handler."
)

REPAIR_PREAMBLE: Final[str] = (
    "Your previous edits were applied and the build or tests then failed. Fix the failure with "
    "further edits. Do not redesign, and do not restate unchanged code - the plan was already "
    "approved and only the defect is in scope."
)


class WriteError(RuntimeError):
    """Raised when the writing stage produces nothing usable."""


def build_request(
    intent: ChangeIntent,
    model: str,
    *,
    template_contract: str | None = None,
    structural_map: str | None = None,
    opened_files: str | None = None,
    diagnostics: str | None = None,
) -> CompletionRequest:
    """Assemble the write call, ordered stable-to-volatile so the prefix stays cacheable.

    `diagnostics` is the repair path. It arrives last precisely because it is the most volatile
    part of the prompt: everything above it survives in the cache across repair attempts.
    """
    messages: list[Message] = [Message(role="system", content=INSTRUCTIONS)]
    if template_contract:
        messages.append(Message(role="system", content=template_contract))
    if structural_map:
        messages.append(Message(role="user", content=structural_map))
    if opened_files:
        messages.append(Message(role="user", content=opened_files))
    messages.append(Message(role="user", content=_render_intent(intent)))
    if diagnostics:
        messages.append(Message(role="user", content=f"{REPAIR_PREAMBLE}\n\n{diagnostics}"))
    return CompletionRequest(
        messages=tuple(messages),
        model=model,
        max_output_tokens=MAX_WRITE_TOKENS,
        temperature=0.0,
    )


def parse(reply: str, existing: dict[str, str] | None = None) -> tuple[EditOperation, ...]:
    """Validate a reply into operations. Rejects the whole batch if any operation is invalid.

    All-or-nothing is deliberate: applying half a batch would leave the solution in a state
    neither the developer nor the next repair attempt reasoned about.
    """
    payload = _extract_object(reply)
    raw = payload.get("operations")
    if not isinstance(raw, list) or not raw:
        raise WriteError("write stage returned no operations")

    sources = existing or {}
    operations: list[EditOperation] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise WriteError(f"operation {index} is not an object")
        try:
            operations.append(parse_operation(item, sources.get(str(item.get("file", "")))))
        except EditOperationError as exc:
            raise WriteError(f"operation {index} ({item.get('file', '?')}): {exc}") from exc
    return tuple(operations)


def produce(
    intent: ChangeIntent,
    provider: Provider,
    model: str,
    *,
    existing: dict[str, str] | None = None,
    template_contract: str | None = None,
    structural_map: str | None = None,
    opened_files: str | None = None,
    diagnostics: str | None = None,
) -> tuple[EditOperation, ...]:
    """Run the write stage once and return validated operations."""
    request = build_request(
        intent,
        model,
        template_contract=template_contract,
        structural_map=structural_map,
        opened_files=opened_files,
        diagnostics=diagnostics,
    )
    return parse(provider.complete(request).text, existing)


def _render_intent(intent: ChangeIntent) -> str:
    lines = ["Approved intent:", intent.summary]
    if intent.rationale:
        lines.extend(("", f"Rationale: {intent.rationale}"))
    if intent.target_files:
        lines.extend(("", "Files: " + ", ".join(intent.target_files)))
    if intent.target_symbols:
        lines.append("Symbols: " + ", ".join(intent.target_symbols))
    return "\n".join(lines)


def _extract_object(reply: str) -> dict:
    text = reply.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1 : -1 if lines[-1].strip().startswith("```") else None])
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise WriteError(f"write stage reply is not a JSON object: {reply[:200]!r}")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise WriteError(f"write stage reply is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise WriteError("write stage reply must be a JSON object")
    return payload
