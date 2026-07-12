# -*- coding: utf-8 -*-
"""Non-interactive `cabal` CLI: argparse layer + apply/doctor/uninstall runners per the 016 CLI contract."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

import cabal
from cabal import _paths, install_manifest
from cabal.install_manifest import ManifestError
from cabal.apply_service import (
    ApplyOutcome,
    PlannedFile,
    UnknownComponentError,
    apply_plan,
    build_plan,
    outcome_summary,
    resolve_component_keys,
)
from cabal.config_doctor import Finding, finding_order, run_doctor
from cabal.manifest_doctor import (
    REPAIRABLE_CATEGORIES,
    ManifestReport,
    manifest_report,
    manifest_status,
)
from cabal.recovery_service import interrupted_state, resume_interrupted
from cabal.uninstall_service import (
    InterruptedInstallError,
    NoManifestError,
    UninstallPlan,
    uninstall,
    uninstall_plan,
    uninstall_summary,
)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_CONFIRMATION_REQUIRED = 3
EXIT_INTERRUPTED = 4
EXIT_NO_MANIFEST = 5


def version_line() -> str:
    return f"cabal {cabal.__version__} ({install_manifest.current_source_mode()})"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cabal",
        description="Deploy and maintain the bundled global/ payload in ~/.claude/.",
    )
    parser.add_argument("--version", action="version", version=version_line())
    sub = parser.add_subparsers(dest="command", required=True)
    apply_parser = sub.add_parser(
        "apply", help="Deploy the bundled global/ payload to ~/.claude/"
    )
    apply_parser.add_argument(
        "--components",
        default=None,
        metavar="KEY[,KEY...]",
        help="Comma-separated component keys (default: all; core is always included)",
    )
    apply_parser.add_argument(
        "--dry-run", action="store_true", help="Print the plan and write nothing"
    )
    apply_parser.add_argument(
        "--yes", action="store_true", help="Proceed without confirmation"
    )
    apply_parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Machine-readable output"
    )
    doctor_parser = sub.add_parser(
        "doctor", help="Health-check ~/.claude against the install manifest"
    )
    doctor_parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Machine-readable output"
    )
    uninstall_parser = sub.add_parser(
        "uninstall", help="Remove the files recorded in the install manifest"
    )
    uninstall_parser.add_argument(
        "--restore-backups",
        action="store_true",
        help="After removal, restore the pre-install backups referenced by the manifest",
    )
    uninstall_parser.add_argument(
        "--dry-run", action="store_true", help="Print the removal plan, delete nothing"
    )
    uninstall_parser.add_argument(
        "--yes", action="store_true", help="Proceed without confirmation"
    )
    uninstall_parser.add_argument(
        "--legacy",
        action="store_true",
        help="No-manifest fallback: remove only registry files matching the bundled source",
    )
    uninstall_parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Machine-readable output"
    )
    return parser


def _emit(args: argparse.Namespace, status: str, outcome: ApplyOutcome) -> None:
    if args.as_json:
        payload = {
            "status": status,
            "tool_version": cabal.__version__,
            "components": outcome.components,
            "counts": {
                "created": outcome.created,
                "updated": outcome.updated,
                "unchanged": outcome.unchanged,
                "backed_up": outcome.backed_up,
                "skipped": outcome.skipped,
            },
            "backup_dir": (
                str(outcome.backup_dir) if outcome.backup_dir is not None else None
            ),
            "manifest": str(outcome.manifest_file),
        }
        print(json.dumps(payload))
        return
    _print_summary(status, outcome)


def _print_plan(plan: Sequence[PlannedFile]) -> None:
    for pf in plan:
        rel = Path(pf.status.rel).as_posix()
        print(f"{pf.status.state:<9} {pf.component}: {rel}")


def _print_summary(status: str, outcome: ApplyOutcome) -> None:
    if status == "applied":
        lines = outcome_summary(outcome)
        print(f"Applied: {lines[0]}.")
        for line in lines[1:]:
            print(line)
    elif status == "up-to-date":
        print(f"Already up to date ({outcome.unchanged} files verified).")
    elif status == "dry-run":
        print(
            f"Dry run: {outcome.created} to create, {outcome.updated} to update, "
            f"{outcome.unchanged} unchanged. Nothing written."
        )
    elif status == "confirmation-required":
        print("Pending changes require confirmation. Re-run with --yes to apply.")
    elif status == "interrupted-detected":
        print(
            "A previous apply was interrupted (manifest status: in_progress). "
            "Re-run with --yes to resume it."
        )


def _run_apply(args: argparse.Namespace) -> int:
    requested = (
        None
        if args.components is None
        else [key.strip() for key in args.components.split(",") if key.strip()]
    )
    try:
        keys = resolve_component_keys(requested)
    except UnknownComponentError as exc:
        print(f"cabal apply: {exc}", file=sys.stderr)
        return EXIT_USAGE
    plan = build_plan(keys)
    preview = apply_plan(plan, dry_run=True)
    pending = preview.created + preview.updated > 0
    if args.dry_run:
        if not args.as_json:
            _print_plan(plan)
        _emit(args, "dry-run", preview)
        return EXIT_OK
    interrupted = interrupted_state() is not None
    if interrupted and not args.yes:
        _emit(args, "interrupted-detected", preview)
        return EXIT_INTERRUPTED
    if not pending and not interrupted:
        _emit(args, "up-to-date", preview)
        return EXIT_OK
    if not args.yes:
        if not args.as_json:
            _print_plan(plan)
        _emit(args, "confirmation-required", preview)
        return EXIT_CONFIRMATION_REQUIRED
    try:
        outcome = resume_interrupted() if interrupted else apply_plan(plan)
    except OSError as exc:
        print(
            f"cabal apply: failed mid-apply, manifest left in_progress: {exc}",
            file=sys.stderr,
        )
        if args.as_json:
            _emit(args, "error", preview)
        return EXIT_FAILURE
    _emit(args, "applied", outcome)
    return EXIT_OK


def _print_findings(findings: Sequence[Finding], report: ManifestReport) -> None:
    if not findings:
        print("Healthy — no findings.")
    for severity in ("error", "warning"):
        group = [f for f in findings if f.severity == severity]
        if not group:
            continue
        print(f"{severity.capitalize()}s:")
        for f in group:
            print(f"  [{f.category}] {f.path} — {f.message}")
    if not report.present:
        print(
            "No install manifest found (legacy install) — "
            "run `cabal apply --yes` to record one."
        )
    if any(f.category in REPAIRABLE_CATEGORIES for f in findings):
        print("Repairable findings — run `cabal apply --yes` to repair.")


def _run_doctor(args: argparse.Namespace) -> int:
    report = manifest_report()
    findings = run_doctor(_paths.TARGET) + report.findings
    findings.sort(key=finding_order)
    if args.as_json:
        payload = {
            "findings": [asdict(f) for f in findings],
            "manifest": {
                "present": report.present,
                "status": report.status,
                "tool_version": report.tool_version,
            },
        }
        print(json.dumps(payload))
    else:
        _print_findings(findings, report)
    if manifest_status() == "absent":
        return EXIT_NO_MANIFEST
    if any(f.severity == "error" for f in findings):
        return EXIT_FAILURE
    return EXIT_OK


_ZERO_UNINSTALL_COUNTS: dict[str, int] = {
    "removed": 0,
    "skipped": 0,
    "missing": 0,
    "restored": 0,
}


def _emit_uninstall_json(args: argparse.Namespace, status: str, counts: dict[str, int]) -> None:
    if args.as_json:
        payload = {
            "status": status,
            "counts": counts,
            "manifest": str(install_manifest.manifest_path()),
        }
        print(json.dumps(payload))


def _print_uninstall_plan(plan: UninstallPlan) -> None:
    for item in plan.remove:
        print(f"REMOVE    {item.component}: {item.rel}")
    for item in plan.skip:
        print(f"KEEP      {item.component}: {item.rel} — {item.reason}")
    for item in plan.missing:
        print(f"MISSING   {item.component}: {item.rel}")
    print(
        f"{len(plan.remove)} to remove, {len(plan.skip)} kept, "
        f"{len(plan.missing)} already missing, "
        f"{len(plan.backups)} backup file(s) restorable."
    )


def _run_uninstall(args: argparse.Namespace) -> int:
    try:
        plan = uninstall_plan(legacy=args.legacy)
    except NoManifestError as exc:
        if not args.as_json:
            print(
                f"cabal uninstall: {exc} (re-run with --legacy to scan components)",
                file=sys.stderr,
            )
        _emit_uninstall_json(args, "no-manifest", dict(_ZERO_UNINSTALL_COUNTS))
        return EXIT_NO_MANIFEST
    except (InterruptedInstallError, ManifestError) as exc:
        print(f"cabal uninstall: {exc}", file=sys.stderr)
        _emit_uninstall_json(args, "error", dict(_ZERO_UNINSTALL_COUNTS))
        return EXIT_FAILURE
    plan_counts = {
        "removed": len(plan.remove),
        "skipped": len(plan.skip),
        "missing": len(plan.missing),
        "restored": 0,
    }
    if args.dry_run:
        if not args.as_json:
            _print_uninstall_plan(plan)
            print("Dry run — nothing removed.")
        _emit_uninstall_json(args, "dry-run", plan_counts)
        return EXIT_OK
    if plan.remove and not args.yes:
        if not args.as_json:
            _print_uninstall_plan(plan)
            print("Removal requires confirmation. Re-run with --yes to uninstall.")
        _emit_uninstall_json(args, "confirmation-required", plan_counts)
        return EXIT_CONFIRMATION_REQUIRED
    result = uninstall(plan, restore_backups=args.restore_backups)
    if not args.as_json:
        for line in uninstall_summary(result):
            print(line)
    status = "error" if result.errors else "uninstalled"
    _emit_uninstall_json(
        args,
        status,
        {
            "removed": len(result.removed),
            "skipped": len(result.skipped),
            "missing": len(result.missing),
            "restored": len(result.restored),
        },
    )
    return EXIT_FAILURE if result.errors else EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    if args.command == "apply":
        return _run_apply(args)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "uninstall":
        return _run_uninstall(args)
    parser.print_usage(sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
