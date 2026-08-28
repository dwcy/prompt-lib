// Package security console screen: severity-colored findings table with a summary/rescan header,
// notices strip (with an inline installer for the pip-audit prerequisite), and the apply_fix /
// install_pip_audit confirm flows — per the cabal-console mock's "Package security check" table
// card (specs/015-web-ui-overhaul/redesign/cabal-console-mock.html, ~lines 313-333).
import { useEffect, useState } from "react";
import { useJob } from "@/api/jobs";
import { type SecurityFinding, useSecurityScan } from "@/api/securityEnvironment";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { useAction } from "@/hooks/useAction";
import { SecurityFindingsTable } from "@/modules/package-security/components/SecurityFindingsTable";
import { SecurityHeader } from "@/modules/package-security/components/SecurityHeader";
import { isPipAuditMissingNotice } from "@/modules/package-security/packageSecurityStatus";
import "./PackageSecurityModule.css";

const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

export function PackageSecurityModule() {
  const [refreshToken, setRefreshToken] = useState(0);
  const scanQuery = useSecurityScan(refreshToken);
  const fixAction = useAction("security.apply_fix");
  const installAction = useAction("security.install_pip_audit");
  const fixJob = useJob(fixAction.jobId ?? "", {
    enabled: fixAction.jobId !== null,
    refetchInterval: 1_000,
  });
  const installJob = useJob(installAction.jobId ?? "", {
    enabled: installAction.jobId !== null,
    refetchInterval: 1_000,
  });

  useEffect(() => {
    if (fixJob.data === undefined || !TERMINAL_STATES.has(fixJob.data.state)) return;
    setRefreshToken((current) => current + 1);
  }, [fixJob.data]);

  useEffect(() => {
    if (installJob.data === undefined || !TERMINAL_STATES.has(installJob.data.state)) return;
    setRefreshToken((current) => current + 1);
  }, [installJob.data]);

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
              <div key={notice} className="pkgsec-notice">
                <span>{notice}</span>
                {isPipAuditMissingNotice(notice) ? (
                  <button type="button" onClick={() => installAction.prepare({})}>
                    Install pip-audit
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
        <SecurityFindingsTable findings={scan.findings} onApplyFix={applyFix} />
      </section>

      {fixAction.jobId !== null ? <JobPane jobId={fixAction.jobId} /> : null}
      {installAction.jobId !== null ? <JobPane jobId={installAction.jobId} /> : null}

      <ConfirmDialog action={fixAction} actionTitle="Apply package security fix" />
      <ConfirmDialog action={installAction} actionTitle="Install pip-audit" />
    </div>
  );
}
