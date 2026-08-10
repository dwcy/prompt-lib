// Shared Package Security console helpers: severity → dot tone, per-kind counts (vulnerable /
// outdated / deprecated) derived client-side from findings (the API summary only exposes
// by_severity / by_ecosystem), and the ecosystem scope description shown in the table header.
import type { SecurityFinding } from "@/api/securityEnvironment";

export type SeverityTone = "ok" | "warning" | "danger" | "neutral";

// A "vulnerable" finding must never render as ok/green, even when the scanner couldn't grade its
// severity (pip-audit reports no severity at all, so python_scanner.py defaults it to "info" —
// which, for an "outdated" or "deprecated" finding, correctly means "nothing to worry about").
// Ungraded/unknown severity on a real vulnerability defaults to danger, not ok, since the absence
// of a grade is not evidence of low risk.
export function severityTone(severity: string, kind: SecurityFinding["kind"]): SeverityTone {
  const value = severity.toLowerCase();
  if (value === "critical" || value === "high") return "danger";
  if (value === "moderate" || value === "medium")
    return kind === "vulnerable" ? "danger" : "warning";
  if (value === "low") return kind === "vulnerable" ? "warning" : "ok";
  if (value === "info") return kind === "vulnerable" ? "danger" : "ok";
  return kind === "vulnerable" ? "danger" : "neutral";
}

const PIP_AUDIT_MISSING_PREFIX = "pip-audit not installed";

export function isPipAuditMissingNotice(notice: string): boolean {
  return notice.startsWith(PIP_AUDIT_MISSING_PREFIX);
}

export interface KindCounts {
  vulnerable: number;
  outdated: number;
  deprecated: number;
}

export function countsByKind(findings: SecurityFinding[]): KindCounts {
  const counts: KindCounts = { vulnerable: 0, outdated: 0, deprecated: 0 };
  for (const finding of findings) {
    if (finding.kind === "vulnerable") counts.vulnerable += 1;
    else if (finding.kind === "outdated") counts.outdated += 1;
    else if (finding.kind === "deprecated") counts.deprecated += 1;
  }
  return counts;
}

const ECOSYSTEM_LABELS: Record<string, string> = {
  dotnet: ".NET",
  npm: "npm/frontend",
  python: "Python",
};

export function ecosystemLabel(ecosystem: string): string {
  return ECOSYSTEM_LABELS[ecosystem] ?? ecosystem;
}

export function scopeDescription(ecosystems: string[]): string {
  if (ecosystems.length === 0) return "No dependency ecosystems detected in this project.";
  const labels = ecosystems.map(ecosystemLabel);
  const joined =
    labels.length === 1
      ? labels[0]
      : `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
  return `${joined} dependencies — runs when a project opens; fixes require confirmation.`;
}
