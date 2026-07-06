"""Command entrypoint for `python -m cabal.okf`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cabal.okf.analytics import analyze_bundle, render_analytics_human
from cabal.okf.context import build_context_pack, render_context_human
from cabal.okf.doctor import doctor_bundle, render_human, render_json
from cabal.okf.exporter import export_okf
from cabal.okf.index import build_index, default_index_path
from cabal.okf.preflight import render_preflight_human, run_preflight
from cabal.okf.recommendations import recommend_from_graph
from cabal.okf.search import search_index_logged
from cabal.okf.semantic import SemanticUnavailableError, semantic_search
from cabal.okf.usage import read_usage, render_usage_human
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

    index = sub.add_parser("index", help="Build the SQLite OKF search index")
    index.add_argument("bundle", help="Bundle root")
    index.add_argument("--db", default=None, help="SQLite database path")
    index.add_argument("--format", choices=("human", "json"), default="human")

    search = sub.add_parser("search", help="Search an OKF SQLite index")
    search.add_argument("db", help="SQLite database path")
    search.add_argument("query", nargs="+", help="Search query")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--type", dest="types", action="append", default=[])
    search.add_argument("--format", choices=("human", "json"), default="human")
    search.add_argument("--usage-path", default=None)
    search.add_argument("--no-usage", action="store_true")

    semantic = sub.add_parser("semantic", help="Semantic search an OKF SQLite index")
    semantic.add_argument("db", help="SQLite database path")
    semantic.add_argument("query", nargs="+", help="Search query")
    semantic.add_argument("--limit", type=int, default=10)
    semantic.add_argument("--format", choices=("human", "json"), default="human")
    semantic.add_argument("--usage-path", default=None)
    semantic.add_argument("--no-usage", action="store_true")

    analytics = sub.add_parser("analytics", help="Analyze an OKF bundle/index")
    analytics.add_argument("bundle", help="Bundle root")
    analytics.add_argument("--db", default=None, help="SQLite database path")
    analytics.add_argument("--previous-db", default=None)
    analytics.add_argument("--incoming-threshold", type=int, default=4)
    analytics.add_argument("--fanout-threshold", type=int, default=6)
    analytics.add_argument("--overlap-threshold", type=int, default=2)
    analytics.add_argument("--format", choices=("human", "json"), default="human")

    context = sub.add_parser("context", help="Build an explicit OKF context pack")
    context.add_argument("db", help="SQLite database path")
    context.add_argument("query", nargs="+", help="Task or retrieval query")
    context.add_argument("--budget", choices=("tiny", "focused", "full"), default="focused")
    context.add_argument("--format", choices=("human", "json"), default="human")
    context.add_argument("--client", choices=("cabal", "claude", "cursor", "unknown"), default="cabal")
    context.add_argument("--usage-path", default=None)
    context.add_argument("--no-usage", action="store_true")

    preflight = sub.add_parser("preflight", help="Show scope/risk/context-budget preflight")
    preflight.add_argument("db", help="SQLite database path")
    preflight.add_argument("task", nargs="+", help="Task text")
    preflight.add_argument("--format", choices=("human", "json"), default="human")
    preflight.add_argument("--client", choices=("cabal", "claude", "cursor", "unknown"), default="cabal")
    preflight.add_argument("--usage-path", default=None)
    preflight.add_argument("--no-usage", action="store_true")

    usage = sub.add_parser("usage", help="Read the local OKF usage ledger")
    usage.add_argument("--path", default=None, help="Usage JSONL path")
    usage.add_argument("--limit", type=int, default=20)
    usage.add_argument("--format", choices=("human", "json"), default="human")

    recommend = sub.add_parser("recommend", help="Recommend agents from graph evidence")
    recommend.add_argument("graph", help="graph.json path")
    recommend.add_argument("query", nargs="+", help="Task text")

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
    if args.command == "index":
        bundle = Path(args.bundle)
        db = build_index(bundle, Path(args.db) if args.db else default_index_path(bundle))
        payload = {"bundle": str(bundle), "db_path": str(db)}
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"OKF index wrote {db}")
        return 0
    if args.command == "search":
        query = " ".join(args.query)
        rows = search_index_logged(
            Path(args.db),
            query,
            client="cabal",
            entrypoint="cli",
            limit=args.limit,
            types=tuple(args.types),
            usage_path=Path(args.usage_path) if args.usage_path else None,
            record_usage=not args.no_usage,
        )
        if args.format == "json":
            print(json.dumps(rows, indent=2, sort_keys=True))
        else:
            for row in rows:
                print(f"{row['id']} [{row['type']}] {row['title']}")
                print(f"  {row['resource']}")
                print(f"  {row['snippet']}")
        return 0 if rows else 1
    if args.command == "semantic":
        query = " ".join(args.query)
        try:
            results = semantic_search(
                Path(args.db),
                query,
                limit=args.limit,
                client="cabal",
                entrypoint="cli",
                usage_path=Path(args.usage_path) if args.usage_path else None,
                record_usage=not args.no_usage,
            )
        except SemanticUnavailableError as exc:
            print(str(exc))
            return 1
        if args.format == "json":
            print(json.dumps(results, indent=2, sort_keys=True))
        else:
            for item in results:
                print(f"{item['id']} [{item['type']}] {item['title']} ({item['score']})")
                print(f"  {item['resource']}")
                print(f"  {item['snippet']}")
        return 0 if results else 1
    if args.command == "analytics":
        report = analyze_bundle(
            Path(args.bundle),
            db_path=Path(args.db) if args.db else None,
            previous_db_path=Path(args.previous_db) if args.previous_db else None,
            incoming_threshold=args.incoming_threshold,
            fanout_threshold=args.fanout_threshold,
            overlap_threshold=args.overlap_threshold,
        )
        print(
            json.dumps(report, indent=2, sort_keys=True)
            if args.format == "json"
            else render_analytics_human(report),
            end="" if args.format == "human" else "\n",
        )
        return 0
    if args.command == "context":
        pack = build_context_pack(
            Path(args.db),
            " ".join(args.query),
            budget=args.budget,
            client=args.client,
            entrypoint="cli",
            usage_path=Path(args.usage_path) if args.usage_path else None,
            record_usage=not args.no_usage,
        )
        print(
            json.dumps(pack, indent=2, sort_keys=True)
            if args.format == "json"
            else render_context_human(pack),
            end="" if args.format == "human" else "\n",
        )
        return 0
    if args.command == "preflight":
        report = run_preflight(
            Path(args.db),
            " ".join(args.task),
            client=args.client,
            entrypoint="cli",
            usage_path=Path(args.usage_path) if args.usage_path else None,
            record_usage=not args.no_usage,
        )
        print(
            json.dumps(report, indent=2, sort_keys=True)
            if args.format == "json"
            else render_preflight_human(report),
            end="" if args.format == "human" else "\n",
        )
        return 0
    if args.command == "usage":
        entries = read_usage(Path(args.path) if args.path else None, limit=args.limit)
        print(
            json.dumps(entries, indent=2, sort_keys=True)
            if args.format == "json"
            else render_usage_human(entries),
            end="" if args.format == "human" else "\n",
        )
        return 0
    if args.command == "recommend":
        recommendations = recommend_from_graph(Path(args.graph), " ".join(args.query))
        print(json.dumps(recommendations, indent=2, sort_keys=True))
        return 0 if recommendations else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
