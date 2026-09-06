# -*- coding: utf-8 -*-
"""Commands that only look: map, providers, report.

None of these can change a solution, which is why they sit apart from the pipeline commands.
`map` writes a cache file and `providers --check` makes a probe call, and both are suppressed
under `--dry-run` so the flag means one thing everywhere.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cabal.dotnetgen import map_cache, reporting, state
from cabal.dotnetgen.exits import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, emit_error, emit_result
from cabal.dotnetgen.providers import config, factory
from cabal.dotnetgen.providers.base import ProviderError


def cmd_map(args: argparse.Namespace) -> int:
    """T041: render the structural map, reusing the cache when the solution has not changed."""
    project = Path(args.project)
    try:
        # `map` only reads the solution, but it does persist a cache file. Under --dry-run even
        # that is skipped, so the flag means the same thing everywhere: nothing on disk changes.
        rendered, built = map_cache.rendered_map(
            project, token_budget=args.budget, write_cache=not args.dry_run
        )
    except state.StateError as exc:
        emit_error(args, str(exc))
        return EXIT_USAGE

    payload: dict[str, object] = {
        "status": "ok",
        "dry_run": bool(args.dry_run),
        "fingerprint": built.fingerprint,
        "token_budget": built.token_budget,
        "estimated_tokens": built.estimated_tokens,
        "types": len(built.entries),
        "omitted_count": built.omitted_count,
        "omitted_summary": built.omitted_summary,
        "map": rendered,
    }
    emit_result(args, payload, rendered)
    return EXIT_OK


def cmd_providers(args: argparse.Namespace) -> int:
    """T056: show what each stage is bound to, and with --check whether it answers.

    Probing costs one token per provider and answers the question that otherwise only surfaces
    halfway through a run: is this configuration actually usable on this machine right now?
    """
    project = Path(args.project)
    try:
        bindings = config.load_bindings(project)
    except config.BindingsError as exc:
        emit_error(args, str(exc))
        return EXIT_USAGE

    stages: list[dict[str, object]] = []
    unreachable = 0
    for stage, binding in sorted(bindings.stages.items()):
        entry: dict[str, object] = {
            "stage": stage,
            "provider": binding.provider,
            "model": binding.model,
            "fallback": binding.fallback.provider if binding.fallback else None,
            "missing_api_key": binding.missing_key(),
        }
        if args.check:
            try:
                status = factory.provider_for(binding).check()
            except ProviderError as exc:
                entry["reachable"] = False
                entry["detail"] = str(exc)
            else:
                entry["reachable"] = status.reachable
                entry["detail"] = status.detail
            if not entry["reachable"]:
                unreachable += 1
        stages.append(entry)

    emit_result(
        args,
        {
            "status": "ok",
            "dry_run": bool(args.dry_run),
            "stages": stages,
            "unreachable": unreachable,
        },
        "\n".join(_provider_line(entry, args.check) for entry in stages),
    )
    # Reporting is the job; an unreachable provider is a finding, not a crash of this command.
    return EXIT_OK if not unreachable else EXIT_FAILURE


def _provider_line(entry: dict[str, object], checked: bool) -> str:
    parts = [f"{entry['stage']:<10} {entry['provider']}/{entry['model']}"]
    if entry["fallback"]:
        parts.append(f"(fallback: {entry['fallback']})")
    if entry["missing_api_key"]:
        parts.append("[api key not set]")
    if checked:
        parts.append("ok" if entry.get("reachable") else f"UNREACHABLE - {entry.get('detail', '')}")
    return " ".join(parts)


def cmd_report(args: argparse.Namespace) -> int:
    """T065: read back recorded runs and show what they cost."""
    project = Path(args.project)
    runs = reporting.load_runs(project)
    selected = reporting.select(runs, run_id=args.run, last=args.last)

    if args.run is not None and not selected:
        emit_error(args, f"no run recorded with id {args.run!r} in {project}")
        return EXIT_USAGE

    emit_result(
        args,
        {
            "status": "ok",
            "dry_run": bool(args.dry_run),
            "runs": [{"run_id": r.run_id, **r.payload} for r in selected],
            "summary": reporting.summarise(selected),
        },
        reporting.render(selected),
    )
    return EXIT_OK
