"""OKF bundle validation."""

from __future__ import annotations

import json
from pathlib import Path

from cabal.okf.frontmatter import extract_frontmatter, parse_frontmatter
from cabal.okf.models import DoctorFinding, DoctorReport
from cabal.okf.paths import normalize_resource


REQUIRED_FILES = ("index.md", "log.md", "manifest.json", "graph.json")
REQUIRED_FIELDS = ("type", "title", "description", "resource", "tags", "timestamp", "id")


def _finding(
    severity: str,
    code: str,
    message: str,
    *,
    resource: str | None = None,
    concept_id: str | None = None,
    relation_id: str | None = None,
    remediation: str | None = None,
) -> DoctorFinding:
    return DoctorFinding(
        severity=severity,
        code=code,
        message=message,
        resource=resource,
        concept_id=concept_id,
        relation_id=relation_id,
        remediation=remediation,
    )


def _load_json(path: Path, findings: list[DoctorFinding]) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        findings.append(
            _finding("error", "OKF001", f"Could not read JSON file: {exc}", resource=path.name)
        )
        return {}


def _relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def doctor_bundle(bundle_root: Path, repo_root: Path) -> DoctorReport:
    bundle_root = Path(bundle_root)
    repo_root = Path(repo_root)
    findings: list[DoctorFinding] = []
    if not bundle_root.exists():
        return DoctorReport(
            ok=False,
            bundle_root=str(bundle_root),
            summary={"documents": 0, "relations": 0, "errors": 1, "warnings": 0, "infos": 0},
            findings=(
                _finding(
                    "error",
                    "OKF001",
                    f"Bundle root missing: {bundle_root}",
                    resource=str(bundle_root),
                ),
            ),
            exit_code=2,
        )

    for required in REQUIRED_FILES:
        if not (bundle_root / required).exists():
            findings.append(
                _finding("error", "OKF001", f"Required generated file missing: {required}", resource=required)
            )

    manifest = _load_json(bundle_root / "manifest.json", findings) if (bundle_root / "manifest.json").exists() else {}
    graph = _load_json(bundle_root / "graph.json", findings) if (bundle_root / "graph.json").exists() else {}
    graph_nodes = {node.get("id"): node for node in graph.get("nodes", []) if isinstance(node, dict)}
    graph_edges = {edge.get("id"): edge for edge in graph.get("edges", []) if isinstance(edge, dict)}

    concept_ids: set[str] = set()
    doc_paths: set[str] = set()
    for path in sorted(bundle_root.rglob("*.md")):
        rel_path = _relative(bundle_root, path)
        text = path.read_text(encoding="utf-8", errors="replace")
        raw_frontmatter, _ = extract_frontmatter(text)
        if not raw_frontmatter:
            findings.append(
                _finding("error", "OKF002", "Required frontmatter missing.", resource=rel_path)
            )
            continue
        frontmatter = parse_frontmatter(raw_frontmatter)
        missing = [field for field in REQUIRED_FIELDS if not frontmatter.get(field)]
        for field in missing:
            findings.append(
                _finding("error", "OKF002", f"Required frontmatter field missing: {field}", resource=rel_path)
            )
        concept_id = str(frontmatter.get("id") or "")
        if concept_id:
            if concept_id in concept_ids:
                findings.append(
                    _finding("error", "OKF004", f"Duplicate concept id: {concept_id}", resource=rel_path, concept_id=concept_id)
                )
            concept_ids.add(concept_id)
        resource = str(frontmatter.get("resource") or "")
        if resource.startswith("docs/okf/"):
            doc_paths.add(rel_path)
            continue
        try:
            normalized = normalize_resource(resource)
        except ValueError:
            findings.append(
                _finding("error", "OKF003", f"Unsafe resource path: {resource}", resource=rel_path, concept_id=concept_id)
            )
            continue
        if normalized and not (repo_root / normalized).exists():
            findings.append(
                _finding(
                    "error",
                    "OKF003",
                    f"Resource path does not exist: {normalized}",
                    resource=rel_path,
                    concept_id=concept_id,
                    remediation="Regenerate the bundle or restore the referenced source file.",
                )
            )
        doc_paths.add(rel_path)

    manifest_files = set(manifest.get("generated_files", []))
    actual_files = {
        _relative(bundle_root, path)
        for path in bundle_root.rglob("*")
        if path.is_file()
    }
    if manifest_files and manifest_files != actual_files:
        findings.append(
            _finding("error", "OKF001", "Manifest file list does not match generated files.", resource="manifest.json")
        )

    graph_node_ids = {node_id for node_id in graph_nodes if node_id}
    reserved_ids = {"index:prompt-lib", "log:prompt-lib"}
    if graph_node_ids != (concept_ids - reserved_ids):
        findings.append(
            _finding("error", "OKF005", "Graph nodes do not match concept documents.", resource="graph.json")
        )

    for edge_id, edge in graph_edges.items():
        if edge.get("source") not in graph_node_ids:
            findings.append(
                _finding("error", "OKF006", f"Graph edge source is missing: {edge.get('source')}", resource="graph.json", relation_id=edge_id)
            )
        target = edge.get("target")
        if target is None:
            findings.append(
                _finding("warning", "OKF101", f"Relation target unresolved: {edge.get('target_ref')}", resource="graph.json", relation_id=edge_id)
            )
        elif target not in graph_node_ids:
            findings.append(
                _finding("error", "OKF006", f"Graph edge target is missing: {target}", resource="graph.json", relation_id=edge_id)
            )

    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = sum(1 for finding in findings if finding.severity == "warning")
    infos = sum(1 for finding in findings if finding.severity == "info")
    summary = {
        "documents": len(doc_paths),
        "relations": len(graph_edges),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
    }
    return DoctorReport(
        ok=errors == 0,
        bundle_root=str(bundle_root),
        summary=summary,
        findings=tuple(sorted(findings, key=lambda item: (item.severity, item.code, item.resource or "", item.message))),
        exit_code=0 if errors == 0 else 1,
    )


def render_json(report: DoctorReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_human(report: DoctorReport) -> str:
    status = "OKF doctor passed" if report.ok else "OKF doctor failed"
    lines = [
        status,
        f"documents: {report.summary.get('documents', 0)}",
        f"relations: {report.summary.get('relations', 0)}",
        f"errors: {report.summary.get('errors', 0)}",
        f"warnings: {report.summary.get('warnings', 0)}",
    ]
    for finding in report.findings:
        where = f" {finding.resource}" if finding.resource else ""
        lines.append(f"{finding.severity.upper()} {finding.code}{where}: {finding.message}")
    return "\n".join(lines) + "\n"
