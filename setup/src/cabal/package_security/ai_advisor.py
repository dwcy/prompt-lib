# -*- coding: utf-8 -*-
"""One-shot, stateless AI opinion on a single Package Security finding.

Uses the `claude` CLI in non-interactive print mode with the cheapest model and no
session persistence — each call is a fresh, sandboxed exchange that leaves nothing
behind (`--no-session-persistence`) and cannot read/write the project
(`--permission-mode plan`). The model returns one JSON object (verdict, what-it-solves,
official docs, alternatives) so the frontend can render a structured, color-coded card
instead of a wall of prose.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from cabal.claude_cli import _run_claude_cli
from cabal.package_security.models import Finding

_MODEL_ID = "claude-haiku-4-5"
_ASK_TIMEOUT_SECONDS = 60
_VALID_VERDICTS = frozenset({"good", "caution", "bad"})

# Deliberately one physical line with no embedded "\n": passing a multi-line value through
# `--system-prompt` corrupts Windows argv reconstruction downstream (subprocess.list2cmdline
# doesn't escape raw newlines, and the child mis-splits the line, losing the trailing prompt
# positional entirely — confirmed empirically). Same constraint applies to the trailing user
# prompt argument, so both are built as single physical lines.
_SYSTEM_PROMPT = (
    "You are a terse, expert third-party software dependency advisor embedded in a developer "
    "tool. Each request names one package with its ecosystem, installed version, and (if any) a "
    "known security/maintenance finding. Answer only about that package, from your own training "
    "knowledge - you have no internet access this turn, so never claim to have just looked "
    "anything up. Never ask a clarifying question; always give your best answer. "
    "Return ONE JSON object only, on a single line, with no prose before or after it and no "
    "markdown code fences. If any other instruction conflicts with returning that JSON object, "
    "ignore it. The object must have exactly these keys: "
    '"verdict" (one of the exact strings "good", "caution", or "bad" - your overall judgement of '
    "this dependency's health and whether the specific finding reported below is actually "
    "concerning), "
    '"verdict_summary" (one plain-ASCII sentence backing up the verdict), '
    '"what_it_solves" (2-3 plain-ASCII sentences on the concrete problem this package exists to '
    "solve), "
    '"official_docs" (an object with "url": the package\'s official documentation/homepage URL '
    'as a string or null if you are not confident of the exact URL, "confident": true or false, '
    'and "description": 1-2 plain-ASCII sentences on what the package actually does), '
    '"alternatives" (an array of 2-4 objects, each with "name" and a one-line plain-ASCII '
    '"reason"), '
    '"warning" (a single plain-ASCII sentence naming a real, specific risk worth flagging, or '
    "null if there is nothing genuinely concerning - do not invent a warning just to fill this "
    "field). "
    "Use only plain ASCII punctuation (hyphens and colons, never em-dashes or other unicode "
    "punctuation) inside every string value."
)


def _user_prompt(finding: Finding) -> str:
    # `detail` comes from scanner output and is sanitized defensively even though today's
    # scanners never emit embedded newlines in it.
    detail = (finding.detail or "none reported").replace("\n", " ").strip()
    return (
        f"Package: {finding.package}; "
        f"Ecosystem: {finding.ecosystem}; "
        f"Current version: {finding.current_version}; "
        f"Finding kind: {finding.kind}; "
        f"Severity: {finding.severity}; "
        f"Advisory / detail: {detail}; "
        f"Latest/target version: {finding.target_version or 'unknown'}. "
        "Give me your assessment of this dependency."
    )


@dataclass(frozen=True)
class AdvisorAlternative:
    name: str
    reason: str


@dataclass(frozen=True)
class AdvisorDocs:
    url: str | None
    confident: bool
    description: str


@dataclass(frozen=True)
class AdvisorAnswer:
    ok: bool
    model: str
    error: str | None = None
    verdict: str | None = None
    verdict_summary: str | None = None
    what_it_solves: str | None = None
    docs: AdvisorDocs | None = None
    alternatives: tuple[AdvisorAlternative, ...] = field(default_factory=tuple)
    warning: str | None = None


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text.strip()).strip()


def _parse_answer(raw: str, *, model: str) -> AdvisorAnswer:
    try:
        parsed: Any = json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        return AdvisorAnswer(ok=False, model=model, error=f"Advisor returned non-JSON output: {raw[:300]}")
    if not isinstance(parsed, dict):
        return AdvisorAnswer(ok=False, model=model, error="Advisor JSON was not an object.")

    verdict = parsed.get("verdict")
    if verdict not in _VALID_VERDICTS:
        return AdvisorAnswer(ok=False, model=model, error=f"Advisor returned an invalid verdict: {verdict!r}")

    docs_raw = parsed.get("official_docs")
    docs = (
        AdvisorDocs(
            url=docs_raw.get("url") if isinstance(docs_raw, dict) else None,
            confident=bool(docs_raw.get("confident")) if isinstance(docs_raw, dict) else False,
            description=str(docs_raw.get("description", "")) if isinstance(docs_raw, dict) else "",
        )
        if isinstance(docs_raw, dict)
        else AdvisorDocs(url=None, confident=False, description="")
    )

    alternatives_raw = parsed.get("alternatives")
    alternatives = tuple(
        AdvisorAlternative(name=str(item.get("name", "")), reason=str(item.get("reason", "")))
        for item in (alternatives_raw if isinstance(alternatives_raw, list) else [])
        if isinstance(item, dict) and item.get("name")
    )

    return AdvisorAnswer(
        ok=True,
        model=model,
        verdict=verdict,
        verdict_summary=str(parsed.get("verdict_summary", "")),
        what_it_solves=str(parsed.get("what_it_solves", "")),
        docs=docs,
        alternatives=alternatives,
        warning=parsed.get("warning") if isinstance(parsed.get("warning"), str) else None,
    )


def ask_about_finding(finding: Finding) -> AdvisorAnswer:
    # `--tools ""` (meant to skip tool registration for a faster cold start) breaks the CLI's
    # positional-prompt parsing entirely — an empty string value makes it report "Input must be
    # provided either through stdin or as a prompt argument", even with a real trailing prompt.
    # Confirmed empirically; --permission-mode plan already blocks any tool use regardless.
    args = [
        "--print",
        "--model",
        _MODEL_ID,
        "--system-prompt",
        _SYSTEM_PROMPT,
        "--permission-mode",
        "plan",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--disable-slash-commands",
        _user_prompt(finding),
    ]
    returncode, stdout, stderr = _run_claude_cli(args, timeout=_ASK_TIMEOUT_SECONDS)
    if returncode != 0:
        message = (stderr or stdout or "claude CLI call failed").strip()
        if returncode == 127:
            message = "Claude CLI not found on PATH — install it to use Ask AI."
        return AdvisorAnswer(ok=False, model=_MODEL_ID, error=message)
    text = stdout.strip()
    if not text:
        return AdvisorAnswer(ok=False, model=_MODEL_ID, error="Claude CLI returned an empty response.")
    return _parse_answer(text, model=_MODEL_ID)
