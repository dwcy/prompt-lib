// Package security console screen: severity-colored findings table with a summary/rescan header,
// notices strip, and the apply_fix confirm flow — per the cabal-console mock's "Package security
// check" table card (specs/015-web-ui-overhaul/redesign/cabal-console-mock.html, ~lines 313-333).
import { useEffect, useState } from "react";
import { useJob } from "@/api/jobs";
import { type SecurityFinding, useSecurityScan } from "@/api/securityEnvironment";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { useAction } from "@/hooks/useAction";
import { SecurityFindingsTable } from "@/modules/package-security/components/SecurityFindingsTable";
import { SecurityHeader } from "@/modules/package-security/components/SecurityHeader";
import "./PackageSecurityModule.css";

const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

export function PackageSecurityModule() {
  const [refreshToken, setRefreshToken] = useState(0);
  const scanQuery = useSecurityScan(refreshToken);
  const fixAction = useAction("security.apply_fix");
  const fixJob = useJob(fixAction.jobId ?? "", {
    enabled: fixAction.jobId !== null,
    refetchInterval: 1_000,
  });

  useEffect(() => {
    if (fixJob.data === undefined || !TERMINAL_STATES.has(fixJob.data.state)) return;
    setRefreshToken((current) => current + 1);
  }, [fixJob.data]);

  if (scanQuery.isPending) return <EmptyState title="Scanning package security…" />;
  if (scanQuery.isError) {
    return <EmptyState title="Package security scan failed" body={scanQuery.error.message} />;
  }

  const scan = scanQuery.data;

  function applyFix(finding: SecurityFinding): void {
    fixAction.prepare({ finding_key: finding.key });
  }

  return (
    <div className="pkgsec-console">
      <section className="pkgsec-card">
        <SecurityHeader
          scan={scan}
          isRescanning={scanQuery.isFetching}
          onRescan={() => setRefreshToken((current) => current + 1)}
        />
        {scan.notices.length > 0 ? (
          <div className="pkgsec-notices">
            {scan.notices.map((notice) => (
              <span key={notice}>{notice}</span>
            ))}
          </div>
        ) : null}
        <SecurityFindingsTable findings={scan.findings} onApplyFix={applyFix} />
      </section>

      {fixAction.jobId !== null ? <JobPane jobId={fixAction.jobId} /> : null}

      <ConfirmDialog
        isOpen={fixAction.phase !== "idle" && fixAction.phase !== "succeeded"}
        actionTitle="Apply package security fix"
        ticket={fixAction.ticket}
        phase={fixAction.phase}
        reviewNotice={fixAction.reviewNotice}
        error={fixAction.error}
        onConfirm={fixAction.confirm}
        onCancel={fixAction.reset}
      />
    </div>
  );
}
