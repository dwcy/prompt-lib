// Severity-colored findings table: dot | PACKAGE | ECOSYSTEM | ADVISORY | CURRENT | LATEST.
// Clicking a row with an automated fix opens the apply_fix confirm flow (existing behavior);
// rows without one are inert but keep their advisory text visible.
import type { SecurityFinding } from "@/api/securityEnvironment";
import { EmptyState } from "@/components/EmptyState";
import { severityTone } from "@/modules/package-security/packageSecurityStatus";

export interface SecurityFindingsTableProps {
  findings: SecurityFinding[];
  onApplyFix: (finding: SecurityFinding) => void;
}

const COLUMN_HEADERS = ["", "PACKAGE", "ECOSYSTEM", "ADVISORY", "CURRENT", "LATEST"];

export function SecurityFindingsTable({ findings, onApplyFix }: SecurityFindingsTableProps) {
  return (
    <div className="pkgsec-table">
      <div className="pkgsec-columns select-none">
        {COLUMN_HEADERS.map((label) => (
          <span key={label || "dot"}>{label}</span>
        ))}
      </div>
      {findings.length === 0 ? (
        <EmptyState title="No package security findings" />
      ) : (
        <div className="pkgsec-rows">
          {findings.map((finding) => (
            <SecurityFindingRow key={finding.key} finding={finding} onApplyFix={onApplyFix} />
          ))}
        </div>
      )}
    </div>
  );
}

interface SecurityFindingRowProps {
  finding: SecurityFinding;
  onApplyFix: (finding: SecurityFinding) => void;
}

function SecurityFindingRow({ finding, onApplyFix }: SecurityFindingRowProps) {
  const tone = severityTone(finding.severity);
  const currentToned = finding.kind === "outdated";
  const hasLatest = finding.target !== null;

  const cells = (
    <>
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
    </>
  );

  if (!finding.fix_available) {
    return (
      <div className="pkgsec-row" title="No automated fix available">
        {cells}
      </div>
    );
  }

  return (
    <button
      type="button"
      className="pkgsec-row pkgsec-row--fixable"
      title={`Apply fix for ${finding.package}`}
      onClick={() => onApplyFix(finding)}
    >
      {cells}
    </button>
  );
}
