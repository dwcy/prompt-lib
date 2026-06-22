"""Data models for the prompt-lib OKF catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceArtifact:
    resource: str
    category: str
    name: str
    exists: bool = True
    sha256: str | None = None


@dataclass(frozen=True)
class EdgeEvidence:
    resource: str
    text: str
    extractor: str
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "line": self.line,
            "text": self.text,
            "extractor": self.extractor,
        }


@dataclass(frozen=True)
class Relation:
    id: str
    kind: str
    source_id: str
    target_ref: str
    confidence: str
    reason: str
    evidence: tuple[EdgeEvidence, ...] = ()
    target_id: str | None = None
    target_resource: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "target_ref": self.target_ref,
            "target_resource": self.target_resource,
            "confidence": self.confidence,
            "reason": self.reason,
            "evidence": [item.to_dict() for item in self.evidence],
        }

    def to_frontmatter(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target_id or self.target_ref,
            "confidence": self.confidence,
            "reason": self.reason,
            "evidence": [item.to_dict() for item in self.evidence],
        }

    def to_graph_edge(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source_id,
            "target": self.target_id,
            "target_ref": self.target_ref,
            "kind": self.kind,
            "confidence": self.confidence,
            "reason": self.reason,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class Backlink:
    source_id: str
    source_title: str
    kind: str
    reason: str
    evidence: tuple[EdgeEvidence, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_title": self.source_title,
            "kind": self.kind,
            "reason": self.reason,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class ConceptDocument:
    id: str
    type: str
    title: str
    description: str
    resource: str
    tags: tuple[str, ...]
    timestamp: str
    path: str
    body: str
    relations: tuple[Relation, ...] = ()
    backlinks: tuple[Backlink, ...] = ()

    def with_relations(
        self,
        relations: tuple[Relation, ...] = (),
        backlinks: tuple[Backlink, ...] = (),
    ) -> "ConceptDocument":
        return ConceptDocument(
            id=self.id,
            type=self.type,
            title=self.title,
            description=self.description,
            resource=self.resource,
            tags=self.tags,
            timestamp=self.timestamp,
            path=self.path,
            body=self.body,
            relations=relations,
            backlinks=backlinks,
        )

    def to_frontmatter(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "resource": self.resource,
            "tags": list(self.tags),
            "timestamp": self.timestamp,
            "id": self.id,
        }
        if self.relations:
            payload["relations"] = [relation.to_frontmatter() for relation in self.relations]
        return payload

    def to_node(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.title,
            "type": self.type,
            "resource": self.resource,
            "doc": self.path,
            "tags": list(self.tags),
            "metrics": {
                "incoming": len(self.backlinks),
                "outgoing": len(self.relations),
                "warnings": 0,
                "errors": 0,
            },
        }


@dataclass(frozen=True)
class DoctorFinding:
    severity: str
    code: str
    message: str
    resource: str | None = None
    concept_id: str | None = None
    relation_id: str | None = None
    remediation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "resource": self.resource,
            "concept_id": self.concept_id,
            "relation_id": self.relation_id,
            "remediation": self.remediation,
        }


@dataclass(frozen=True)
class DoctorReport:
    ok: bool
    bundle_root: str
    summary: dict[str, int]
    findings: tuple[DoctorFinding, ...] = ()
    exit_code: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "bundle_root": self.bundle_root,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class ExportResult:
    bundle_root: str
    generated_files: tuple[str, ...]
    document_count: int
    relation_count: int
    source_categories: dict[str, int] = field(default_factory=dict)
