# -*- coding: utf-8 -*-
"""The stage-bindable provider interface every auth path implements.

Usage reporting is the load-bearing part of this interface, not an afterthought: `cached_input`
feeds SC-005 (cache ratio) and SC-010 (ledger reconciliation). A provider that cannot report
cached input tokens silently forfeits both, so `Usage.cache_reported` makes that explicit
rather than letting a zero masquerade as a measurement.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """A provider call failed. Carries whether a retry or fallback could plausibly help."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ProviderUnavailableError(ProviderError):
    """The provider could not be reached or authenticated at all — fall back if one is configured."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=True)


def post_json(url: str, body: dict, headers: dict[str, str], timeout: int) -> dict:
    """POST one JSON document and map every failure mode onto the provider errors.

    Shared by the HTTP adapters so the exception mapping cannot drift between them: 429 and 5xx
    are retryable because those are exactly the cases a configured fallback exists for (FR-027).
    """
    request = urllib.request.Request(
        url=url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        retryable = exc.code in (408, 409, 429) or exc.code >= 500
        raise ProviderError(
            f"{url} returned HTTP {exc.code}: {detail}", retryable=retryable
        ) from exc
    except urllib.error.URLError as exc:
        raise ProviderUnavailableError(f"cannot reach {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderError(f"{url} timed out after {timeout}s", retryable=True) from exc
    except json.JSONDecodeError as exc:
        raise ProviderError(f"{url} returned malformed JSON: {exc}") from exc


@dataclass(frozen=True)
class Usage:
    """Token accounting for one call. All counts are as reported by the provider, never estimated."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_reported: bool = True

    @property
    def uncached_input_tokens(self) -> int:
        return max(0, self.input_tokens - self.cached_input_tokens)

    @property
    def cache_ratio(self) -> float | None:
        """Cached share of input tokens, or None when the provider does not report caching."""
        if not self.cache_reported or self.input_tokens <= 0:
            return None
        return self.cached_input_tokens / self.input_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            cache_reported=self.cache_reported and other.cache_reported,
        )


@dataclass(frozen=True)
class Message:
    """One conversation turn. `cache_checkpoint` marks a prefix boundary worth caching."""

    role: str
    content: str
    cache_checkpoint: bool = False


@dataclass(frozen=True)
class CompletionRequest:
    """A single stage's call. `messages` arrives pre-ordered stable-to-volatile by `context.bands`."""

    messages: tuple[Message, ...]
    model: str
    max_output_tokens: int | None = None
    temperature: float | None = None
    stop: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class CompletionResult:
    """What a provider returns: the text, the usage, and which model actually served it."""

    text: str
    usage: Usage
    model: str
    provider: str
    wall_clock_seconds: float = 0.0
    provider_cost_usd: float | None = None
    """The cost the provider itself reported, or None when it reports no figure.

    SC-010 reconciles our arithmetic against this. None is load-bearing: comparing our total to
    a number we computed ourselves would be a guaranteed-pass check that proves nothing.
    """


@runtime_checkable
class Provider(Protocol):
    """Implemented by every provider module. Stages depend on this, never on a concrete adapter."""

    name: str

    def complete(self, request: CompletionRequest) -> CompletionResult:
        """Run one completion. Raises `ProviderError` on failure."""
        ...

    def check(self) -> "ProviderStatus":
        """Probe reachability without running a completion. Must not raise."""
        ...


@dataclass(frozen=True)
class ProviderStatus:
    """Outcome of a reachability probe, for `providers --check`."""

    provider: str
    model: str
    reachable: bool
    detail: str = ""

    def line(self) -> str:
        mark = "ok" if self.reachable else "FAIL"
        suffix = f" - {self.detail}" if self.detail else ""
        return f"{mark:4} {self.provider}/{self.model}{suffix}"
