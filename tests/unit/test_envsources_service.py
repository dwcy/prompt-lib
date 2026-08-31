# -*- coding: utf-8 -*-
"""T007: the fan-out contract — a hanging or raising collector degrades, it never propagates."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from cabal.models.envsources import AvailabilityState, SourceKind, VariableSource
from cabal.webapi.envsources_service import CollectorSpec, fan_out


def _spec(name: str, collect) -> CollectorSpec:
    return CollectorSpec(id=f"{name}:0", kind=SourceKind.GITHUB, label=name, collect=collect)


def _ok_source(name: str) -> VariableSource:
    return VariableSource(
        id=f"{name}:0", kind=SourceKind.GITHUB, label=name, state=AvailabilityState.OK
    )


def test_a_hanging_collector_does_not_delay_the_response_past_the_cap() -> None:
    release = threading.Event()

    def hangs(_project: Path) -> list[VariableSource]:
        release.wait(30)
        return []

    started = time.monotonic()
    try:
        sources = fan_out(
            [_spec("slow", hangs), _spec("fast", lambda _p: [_ok_source("fast")])],
            Path("."),
            total_timeout_s=0.3,
        )
        elapsed = time.monotonic() - started
    finally:
        release.set()

    assert elapsed < 2.0
    slow, fast = sources
    assert slow.state is AvailabilityState.DEGRADED
    assert "did not respond" in (slow.hint or "")
    assert fast.state is AvailabilityState.OK


def test_a_raising_collector_yields_degraded_with_a_hint() -> None:
    def explodes(_project: Path) -> list[VariableSource]:
        raise RuntimeError("gh exited 128")

    (source,) = fan_out([_spec("github", explodes)], Path("."), total_timeout_s=1.0)

    assert source.state is AvailabilityState.DEGRADED
    assert "gh exited 128" in (source.hint or "")
    assert source.label == "github"


def test_a_raising_collector_does_not_stop_its_neighbours() -> None:
    def explodes(_project: Path) -> list[VariableSource]:
        raise OSError("az not found")

    sources = fan_out(
        [_spec("azure", explodes), _spec("vercel", lambda _p: [_ok_source("vercel")])],
        Path("."),
        total_timeout_s=1.0,
    )

    assert [source.state for source in sources] == [
        AvailabilityState.DEGRADED,
        AvailabilityState.OK,
    ]


def test_sources_come_back_in_spec_order_regardless_of_completion_order() -> None:
    def slow_ok(_project: Path) -> list[VariableSource]:
        time.sleep(0.05)
        return [_ok_source("first")]

    sources = fan_out(
        [_spec("first", slow_ok), _spec("second", lambda _p: [_ok_source("second")])],
        Path("."),
        total_timeout_s=1.0,
    )

    assert [source.label for source in sources] == ["first", "second"]


def test_an_empty_spec_list_is_not_an_error() -> None:
    assert fan_out([], Path(".")) == []


def test_collectors_run_concurrently_rather_than_one_after_another() -> None:
    def sleeps(_project: Path) -> list[VariableSource]:
        time.sleep(0.15)
        return [_ok_source("x")]

    started = time.monotonic()
    sources = fan_out(
        [_spec(f"c{index}", sleeps) for index in range(3)], Path("."), total_timeout_s=2.0
    )
    elapsed = time.monotonic() - started

    assert all(source.state is AvailabilityState.OK for source in sources)
    assert elapsed < 0.40
