# -*- coding: utf-8 -*-
"""Anthropic Messages adapter, for the API-key auth mode.

The reason this exists alongside the CLI-shell adapter is cache accounting. SC-005 asks that at
least 70% of served context come from cache across a run sequence, and SC-010 asks that our cost
arithmetic reconcile with the provider's own figures. Both need the *cache* token counts, which
this API reports directly as `cache_read_input_tokens` and `cache_creation_input_tokens`.

The banded prompt is what makes those numbers move: `context.bands` orders content stable-to-
volatile and marks checkpoints, and this adapter turns those checkpoints into `cache_control`
markers. Without that, the prefix is re-sent in full every turn and the cache reports zero.

Uses `urllib` from the standard library, matching `openai_compatible` - the pipeline should not
take a runtime dependency to POST one JSON document.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final

from cabal.dotnetgen.providers.base import (
    CompletionRequest,
    CompletionResult,
    Message,
    ProviderError,
    ProviderStatus,
    post_json,
)
from cabal.dotnetgen.providers.config import StageBinding
from cabal.dotnetgen.providers.usage import parse_usage

PROVIDER_NAME: Final[str] = "anthropic"
DEFAULT_BASE_URL: Final[str] = "https://api.anthropic.com"
API_VERSION: Final[str] = "2023-06-01"
REQUEST_TIMEOUT_SECONDS: Final[int] = 300
CHECK_TIMEOUT_SECONDS: Final[int] = 10
DEFAULT_MAX_TOKENS: Final[int] = 4096


@dataclass(frozen=True)
class AnthropicProvider:
    """Stage-bindable adapter. Holds no key: the binding reads it from the environment per call."""

    binding: StageBinding
    name: str = PROVIDER_NAME

    @property
    def base_url(self) -> str:
        return (self.binding.base_url or DEFAULT_BASE_URL).rstrip("/")

    @property
    def is_local(self) -> bool:
        """Never local. Present so the ledger can ask every provider the same question."""
        return False

    def _headers(self) -> dict[str, str]:
        key = self.binding.api_key()
        if not key:
            raise ProviderError(
                f"{self.binding.api_key_env or 'ANTHROPIC_API_KEY'} is not set; "
                f"stage {self.binding.stage!r} cannot authenticate"
            )
        return {
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": API_VERSION,
        }

    def _post(self, path: str, body: dict, timeout: int) -> dict:
        return post_json(f"{self.base_url}{path}", body, self._headers(), timeout)

    def complete(self, request: CompletionRequest) -> CompletionResult:
        system, messages = _split_system(request)
        body: dict = {
            "model": request.model,
            "max_tokens": request.max_output_tokens or DEFAULT_MAX_TOKENS,
            "messages": messages,
        }
        if system:
            body["system"] = system
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.stop:
            body["stop_sequences"] = list(request.stop)

        started = time.monotonic()
        payload = self._post("/v1/messages", body, REQUEST_TIMEOUT_SECONDS)
        elapsed = time.monotonic() - started

        blocks = payload.get("content")
        if not isinstance(blocks, list):
            raise ProviderError(f"response contained no content: {str(payload)[:300]}")
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

        return CompletionResult(
            text=text,
            usage=parse_usage(payload.get("usage")),
            model=payload.get("model", request.model),
            provider=self.name,
            wall_clock_seconds=elapsed,
        )

    def check(self) -> ProviderStatus:
        """Probe with a one-token call. Cheaper than a health endpoint the API does not offer."""
        try:
            self._post(
                "/v1/messages",
                {
                    "model": self.binding.model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                },
                CHECK_TIMEOUT_SECONDS,
            )
        except ProviderError as exc:
            return ProviderStatus(self.name, self.binding.model, reachable=False, detail=str(exc))
        return ProviderStatus(self.name, self.binding.model, reachable=True)


def _split_system(request: CompletionRequest) -> tuple[str | list[dict], list[dict]]:
    """Anthropic takes system content as its own field, not as a message role.

    The leading system blocks are the stable bands, so hoisting them here is also what keeps the
    cacheable prefix contiguous. A `cache_checkpoint` marks where that prefix ends, and it is
    honoured here as a `cache_control` marker - the request-side half of what the module
    docstring promises. When any system part carries a checkpoint the system field must stay a
    block list, because joining the parts into one string would erase the checkpoint boundary.
    """
    system_parts: list[Message] = []
    messages: list[dict] = []
    for message in request.messages:
        if message.role == "system" and not messages:
            system_parts.append(message)
            continue
        messages.append({"role": message.role, "content": _content(message)})
    if not messages:
        # The API requires at least one message; an all-system request is still a real request.
        last = system_parts.pop() if system_parts else None
        messages.append({"role": "user", "content": _content(last) if last else ""})

    system: str | list[dict]
    if any(part.cache_checkpoint for part in system_parts):
        system = [_block(part) for part in system_parts]
    else:
        system = "\n\n".join(part.content for part in system_parts)
    return system, messages


def _content(message: Message) -> str | list[dict]:
    """Plain string unless a checkpoint forces the block form that can carry `cache_control`."""
    if not message.cache_checkpoint:
        return message.content
    return [_block(message)]


def _block(message: Message) -> dict:
    block: dict = {"type": "text", "text": message.content}
    if message.cache_checkpoint:
        block["cache_control"] = {"type": "ephemeral"}
    return block
