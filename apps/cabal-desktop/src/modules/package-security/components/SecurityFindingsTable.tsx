// Severity-colored findings table: dot | PACKAGE | ECOSYSTEM | ADVISORY | CURRENT | LATEST | actions.
// The Fix button (only on findings with an automated fix) opens the apply_fix confirm flow
// (existing behavior); Ask AI is an accordion — expanding one collapses any other, since each ask
// is a real, billed CLI call and running several at once would be wasteful.
import { useState } from "react";
import type { SecurityFinding } from "@/api/securityEnvironment";
import { EmptyState } from "@/components/EmptyState";
import { PackageAiAdvisor } from "@/modules/package-security/components/PackageAiAdvisor";
import { severityTone } from "@/modules/package-security/packageSecurityStatus";

export interface SecurityFindingsTableProps {
  findings: SecurityFinding[];
  onApplyFix: (finding: SecurityFinding) => void;
}

const COLUMN_HEADERS = ["", "PACKAGE", "ECOSYSTEM", "ADVISORY", "CURRENT", "LATEST", ""];

export function SecurityFindingsTable({ findings, onApplyFix }: SecurityFindingsTableProps) {
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  return (
    <div className="pkgsec-table">
      <div className="pkgsec-columns select-none">
        {COLUMN_HEADERS.map((label, index) => (
          <span key={label || `col-${index}`}>{label}</span>
        ))}
      </div>
      {findings.length === 0 ? (
        <EmptyState title="No package security findings" />
      ) : (
        <div className="pkgsec-rows">
          {findings.map((finding) => (
            <SecurityFindingRow
              key={finding.key}
              finding={finding}
              onApplyFix={onApplyFix}
              isExpanded={expandedKey === finding.key}
              onToggleAi={() =>
                setExpandedKey((current) => (current === finding.key ? null : finding.key))
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface SecurityFindingRowProps {
  finding: SecurityFinding;
  onApplyFix: (finding: SecurityFinding) => void;
  isExpanded: boolean;
  onToggleAi: () => void;
}

function SecurityFindingRow({
  finding,
  onApplyFix,
  isExpanded,
  onToggleAi,
}: SecurityFindingRowProps) {
  const tone = severityTone(finding.severity, finding.kind);
  const currentToned = finding.kind === "outdated";
  const hasLatest = finding.target !== null;

  return (
    <>
      <div className="pkgsec-row" title={finding.detail || undefined}>
        <span
          className={`pkgsec-dot pkgsec-dot--${tone}`}
          role="img"
          aria-label={`${finding.severity} severity`}
          title={finding.severity}
        />
        <span className="pkgsec-row__package">{finding.package}</span>
        <span className="pkgsec-row__ecosystem">{finding.ecosystem}</span>
        <span className="pkgsec-row__advisory">{finding.detail || "No detail supplied."}</span>
        <span className={`pkgsec-row__current${currentToned ? " is-warning" : ""}`}>
          {finding.current}
        </span>
        <span className={`pkgsec-row__latest${hasLatest ? " is-ok" : ""}`}>
          {finding.target ?? "—"}
        </span>
        <span className="pkgsec-row__actions">
          {finding.fix_available ? (
            <button
              type="button"
              className="pkgsec-row__fix"
              title={`Apply fix for ${finding.package}`}
              onClick={() => onApplyFix(finding)}
            >
              Fix
            </button>
          ) : null}
          <button
            type="button"
            className="pkgsec-row__ask"
            aria-pressed={isExpanded}
            onClick={onToggleAi}
          >
            {isExpanded ? "Hide AI" : "Ask AI"}
          </button>
        </span>
      </div>
      {isExpanded ? (
        <PackageAiAdvisor findingKey={finding.key} packageName={finding.package} />
      ) : null}
    </>
  );
}
