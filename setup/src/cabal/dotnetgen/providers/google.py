# -*- coding: utf-8 -*-
"""Google Gemini adapter, normalised onto the shared provider interface.

Gemini's wire format differs from both other adapters in three ways that matter here, so the
translation is the whole job: roles are `user`/`model` rather than `user`/`assistant`, content is
a list of parts rather than a string, and system instructions are a separate top-level field.

Cache reporting is partial. The API reports `cachedContentTokenCount` only when explicit context
caching is in use; an ordinary call omits it. That absence is preserved as
`cache_reported=False` rather than recorded as zero, because a zero would be indistinguishable
from "the cache genuinely served nothing" and would drag SC-005 down with a number nobody measured.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Final

from cabal.dotnetgen.providers.base import (
    CompletionRequest,
    CompletionResult,
    ProviderError,
    ProviderStatus,
    ProviderUnavailableError,
    Usage,
    post_json,
)
from cabal.dotnetgen.providers.config import StageBinding

PROVIDER_NAME: Final[str] = "google"
DEFAULT_BASE_URL: Final[str] = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_SECONDS: Final[int] = 300
CHECK_TIMEOUT_SECONDS: Final[int] = 10


@dataclass(frozen=True)
class GoogleProvider:
    """Stage-bindable adapter. Holds no key: the binding reads it from the environment per call."""

    binding: StageBinding
    name: str = PROVIDER_NAME

    @property
    def base_url(self) -> str:
        return (self.binding.base_url or DEFAULT_BASE_URL).rstrip("/")

    @property
    def is_local(self) -> bool:
        return False

    def _key(self) -> str:
        key = self.binding.api_key()
        if not key:
            raise ProviderError(
                f"{self.binding.api_key_env or 'GEMINI_API_KEY'} is not set; "
                f"stage {self.binding.stage!r} cannot authenticate"
            )
        return key

    def _post(self, model: str, body: dict, timeout: int) -> dict:
        url = f"{self.base_url}/models/{urllib.parse.quote(model)}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._key()}
        return post_json(url, body, headers, timeout)


    def complete(self, request: CompletionRequest) -> CompletionResult:
        system, contents = _split_system(request)
        body: dict = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        generation: dict = {}
        if request.max_output_tokens is not None:
            generation["maxOutputTokens"] = request.max_output_tokens
        if request.temperature is not None:
            generation["temperature"] = request.temperature
        if request.stop:
            generation["stopSequences"] = list(request.stop)
        if generation:
            body["generationConfig"] = generation

        started = time.monotonic()
        payload = self._post(request.model, body, REQUEST_TIMEOUT_SECONDS)
        elapsed = time.monotonic() - started

        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderError(f"response contained no candidates: {str(payload)[:300]}")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))

        return CompletionResult(
            text=text,
            usage=_usage_from(payload.get("usageMetadata")),
            model=payload.get("modelVersion", request.model),
            provider=self.name,
            wall_clock_seconds=elapsed,
        )

    def check(self) -> ProviderStatus:
        try:
            self._post(
                self.binding.model,
                {
                    "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
                    "generationConfig": {"maxOutputTokens": 1},
                },
                CHECK_TIMEOUT_SECONDS,
            )
        except ProviderError as exc:
            return ProviderStatus(self.name, self.binding.model, reachable=False, detail=str(exc))
        return ProviderStatus(self.name, self.binding.model, reachable=True)


def _split_system(request: CompletionRequest) -> tuple[str, list[dict]]:
    """Hoist leading system content and translate roles: `assistant` becomes `model`."""
    system_parts: list[str] = []
    contents: list[dict] = []
    for message in request.messages:
        if message.role == "system" and not contents:
            system_parts.append(message.content)
            continue
        role = "model" if message.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message.content}]})
    if not contents:
        contents.append(
            {"role": "user", "parts": [{"text": system_parts.pop() if system_parts else ""}]}
        )
    return "\n\n".join(system_parts), contents


def _usage_from(raw: object) -> Usage:
    """Normalise `usageMetadata`, preserving 'not reported' rather than inventing a zero."""
    if not isinstance(raw, dict):
        return Usage(cache_reported=False)
    cached_raw = raw.get("cachedContentTokenCount")
    return Usage(
        input_tokens=int(raw.get("promptTokenCount", 0) or 0),
        output_tokens=int(raw.get("candidatesTokenCount", 0) or 0),
        cached_input_tokens=int(cached_raw or 0),
        cache_reported=cached_raw is not None,
    )
