"""Command entrypoint for `python -m cabal.okf`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cabal.okf.analytics import analyze_bundle
from cabal.okf.doctor import doctor_bundle, render_human, render_json
from cabal.okf.exporter import export_okf
from cabal.okf.index import build_index
from cabal.okf.recommendations import recommend_from_graph
from cabal.okf.viewer import generate_viewer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m cabal.okf")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="Generate the prompt-lib OKF bundle")
    export.add_argument("--repo", default=".", help="Repository root")
    export.add_argument("--out", default=None, help="Output bundle root")
    export.add_argument("--timestamp", default=None, help="Fixed generation timestamp")

    doctor = sub.add_parser("doctor", help="Validate an OKF bundle")
    doctor.add_argument("bundle", help="Bundle root")
    doctor.add_argument("--repo", default=".", help="Repository root")
    doctor.add_argument("--format", choices=("human", "json"), default="human")

    graph = sub.add_parser("graph", help="Generate a static graph viewer")
    graph.add_argument("--graph", default="docs/okf/prompt-lib/graph.json")
    graph.add_argument("--out", default="docs/okf/prompt-lib/graph.html")

    recommend = sub.add_parser("recommend", help="Recommend agents from graph evidence")
    recommend.add_argument("graph", help="graph.json path")
    recommend.add_argument("query", nargs="+", help="Task text")

    index = sub.add_parser("index", help="Build the SQLite search index for a bundle")
    index.add_argument("bundle", help="Bundle root")
    index.add_argument("--db", default=None, help="Output SQLite index path")

    analytics = sub.add_parser(
        "analytics", help="Compute analytics for an indexed bundle"
    )
    analytics.add_argument("bundle", help="Bundle root")
    analytics.add_argument("--db", default=None, help="SQLite index path")
    analytics.add_argument("--format", choices=("json",), default="json")
    analytics.add_argument("--incoming-threshold", type=int, default=1)
    analytics.add_argument("--fanout-threshold", type=int, default=2)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export":
        result = export_okf(
            Path(args.repo),
            Path(args.out) if args.out else None,
            generated_at=args.timestamp,
        )
        print(
            f"OKF export wrote {result.document_count} documents and {result.relation_count} relations to {result.bundle_root}"
        )
        return 0
    if args.command == "doctor":
        report = doctor_bundle(Path(args.bundle), Path(args.repo))
        print(
            render_json(report) if args.format == "json" else render_human(report),
            end="",
        )
        return report.exit_code
    if args.command == "graph":
        viewer = generate_viewer(Path(args.graph), Path(args.out))
        print(str(viewer))
        return 0
    if args.command == "recommend":
        recommendations = recommend_from_graph(Path(args.graph), " ".join(args.query))
        print(json.dumps(recommendations, indent=2, sort_keys=True))
        return 0 if recommendations else 1
    if args.command == "index":
        db = build_index(Path(args.bundle), Path(args.db) if args.db else None)
        print(str(db))
        return 0
    if args.command == "analytics":
        report = analyze_bundle(
            Path(args.bundle),
            db_path=Path(args.db) if args.db else None,
            incoming_threshold=args.incoming_threshold,
            fanout_threshold=args.fanout_threshold,
        )
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
