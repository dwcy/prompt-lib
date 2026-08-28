"""Time-bounded memoization for the host probes behind polled webapi endpoints.

Health is polled every 5s per client and the overview runs ~15 sequential
`--version` probes plus a network `git ls-remote`; the underlying helpers stay
uncached so the TUI and CLI keep reading live state.
"""

from __future__ import annotations

import functools
import threading
import time
from collections.abc import Callable
from typing import Any

DRIFT_TTL_S = 30.0
BRANCH_TTL_S = 30.0
ENVIRONMENT_TTL_S = 300.0
UPDATES_TTL_S = 300.0

_registry: list[Callable[[], None]] = []


def ttl_cached(seconds: float) -> Callable:
    """Memoize a callable with hashable args for `seconds`."""

    def decorator(func: Callable) -> Callable:
        lock = threading.Lock()
        cache: dict[tuple, tuple[float, Any]] = {}

        @functools.wraps(func)
        def wrapper(*args):
            now = time.monotonic()
            with lock:
                hit = cache.get(args)
                if hit is not None and now - hit[0] < seconds:
                    return hit[1]
            value = func(*args)
            with lock:
                cache[args] = (time.monotonic(), value)
            return value

        def clear() -> None:
            with lock:
                cache.clear()

        wrapper.cache_clear = clear  # type: ignore[attr-defined]
        _registry.append(clear)
        return wrapper

    return decorator


def clear_probe_caches() -> None:
    """Drop every memoized probe result; tests call this between cases."""
    for clear in _registry:
        clear()
