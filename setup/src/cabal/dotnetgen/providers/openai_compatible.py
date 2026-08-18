# -*- coding: utf-8 -*-
"""OpenAI chat-completions adapter, selected by `base_url`.

One implementation covers three deployments because they speak the same wire format:
    Ollama     http://localhost:11434/v1   (no key, zero cost)
    LM Studio  http://localhost:1234/v1    (no key, zero cost)
    hosted     https://api.openai.com/v1   (needs api_key_env)

Uses `urllib` from the standard library rather than an HTTP client package: the pipeline should
not add a runtime dependency to POST one JSON document.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final

from cabal.dotnetgen.providers.base import (
    CompletionRequest,
    CompletionResult,
    ProviderError,
    ProviderStatus,
    ProviderUnavailableError,
)
from cabal.dotnetgen.providers.config import StageBinding
from cabal.dotnetgen.providers.usage import parse_usage

PROVIDER_NAME: Final[str] = "openai_compatible"
REQUEST_TIMEOUT_SECONDS: Final[int] = 300
CHECK_TIMEOUT_SECONDS: Final[int] = 5

# Hosts whose tokens are free because the model runs on this machine.
_LOCAL_HOSTS: Final[frozenset[str]] = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    """Stage-bindable adapter. Holds no key: the binding reads it from the environment per call."""

    binding: StageBinding
    name: str = PROVIDER_NAME

    @property
    def base_url(self) -> str:
        if not self.binding.base_url:
            raise ProviderError(
                f"stage {self.binding.stage!r} binds {PROVIDER_NAME} but sets no base_url"
            )
        return self.binding.base_url.rstrip("/")

    @property
    def is_local(self) -> bool:
        """Local endpoints incur no per-token cost, which is what SC-008 measures."""
        from urllib.parse import urlparse

        host = urlparse(self.base_url).hostname or ""
        return host in _LOCAL_HOSTS

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key = self.binding.api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        elif self.binding.requires_api_key:
            raise ProviderError(
                f"{self.binding.api_key_env} is not set; "
                f"stage {self.binding.stage!r} cannot authenticate"
            )
        return headers

    def _post(self, path: str, body: dict, timeout: int) -> dict:
        request = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            retryable = exc.code in (408, 409, 429) or exc.code >= 500
            raise ProviderError(
                f"{self.base_url}{path} returned HTTP {exc.code}: {detail}",
                retryable=retryable,
            ) from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailableError(f"cannot reach {self.base_url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ProviderError(f"{self.base_url} timed out after {timeout}s", retryable=True) from exc
        except json.JSONDecodeError as exc:
            raise ProviderError(f"{self.base_url} returned malformed JSON: {exc}") from exc

    def complete(self, request: CompletionRequest) -> CompletionResult:
        body: dict = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
        }
        if request.max_output_tokens is not None:
            body["max_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.stop:
            body["stop"] = list(request.stop)

        started = time.monotonic()
        payload = self._post("/chat/completions", body, REQUEST_TIMEOUT_SECONDS)
        elapsed = time.monotonic() - started

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError(f"response contained no choices: {str(payload)[:300]}")
        message = choices[0].get("message") or {}
        text = message.get("content")
        if not isinstance(text, str):
            raise ProviderError("response choice carried no text content")

        return CompletionResult(
            text=text,
            usage=parse_usage(payload.get("usage")),
            model=payload.get("model", request.model),
            provider=self.name,
            wall_clock_seconds=elapsed,
        )

    def check(self) -> ProviderStatus:
        """Probe `/models` for reachability. Never raises — this is the diagnostic path."""
        try:
            request = urllib.request.Request(
                url=f"{self.base_url}/models", headers=self._headers(), method="GET"
            )
            with urllib.request.urlopen(request, timeout=CHECK_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ProviderError) as exc:
            return ProviderStatus(
                provider=self.name, model=self.binding.model, reachable=False, detail=str(exc)
            )

        available = {
            entry.get("id")
            for entry in payload.get("data", [])
            if isinstance(entry, dict)
        }
        if available and self.binding.model not in available:
            return ProviderStatus(
                provider=self.name,
                model=self.binding.model,
                reachable=False,
                detail=f"endpoint is up but model is not available (has {len(available)} others)",
            )
        return ProviderStatus(provider=self.name, model=self.binding.model, reachable=True)
