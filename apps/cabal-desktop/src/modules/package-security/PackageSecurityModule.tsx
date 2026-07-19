import { useEffect, useMemo, useState } from "react";
import { useJob } from "@/api/jobs";
import { type SecurityFinding, useSecurityScan } from "@/api/securityEnvironment";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";

const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

export function PackageSecurityModule() {
  const [refreshToken, setRefreshToken] = useState(0);
  const [severity, setSeverity] = useState("all");
  const [ecosystem, setEcosystem] = useState("all");
  const [fixableOnly, setFixableOnly] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const scanQuery = useSecurityScan(refreshToken);
  const fixAction = useAction("security.apply_fix");
  const fixJob = useJob(fixAction.jobId ?? "", {
    enabled: fixAction.jobId !== null,
    refetchInterval: 1_000,
  });

  const findings = scanQuery.data?.findings ?? [];
  const ecosystems = useMemo(
    () => ["all", ...Array.from(new Set(findings.map((finding) => finding.ecosystem))).sort()],
    [findings],
  );
  const severities = useMemo(
    () => ["all", ...Array.from(new Set(findings.map((finding) => finding.severity))).sort()],
    [findings],
  );
  const visibleFindings = useMemo(
    () =>
      findings.filter(
        (finding) =>
          (severity === "all" || finding.severity === severity) &&
          (ecosystem === "all" || finding.ecosystem === ecosystem) &&
          (!fixableOnly || finding.fix_available),
      ),
    [ecosystem, findings, fixableOnly, severity],
  );
  const selectedFinding =
    visibleFindings.find((finding) => finding.key === selectedKey) ?? visibleFindings[0] ?? null;

  useEffect(() => {
    if (selectedKey !== null && visibleFindings.some((finding) => finding.key === selectedKey)) {
      return;
    }
    setSelectedKey(visibleFindings[0]?.key ?? null);
  }, [selectedKey, visibleFindings]);

  useEffect(() => {
    if (fixJob.data === undefined || !TERMINAL_STATES.has(fixJob.data.state)) return;
    setRefreshToken((current) => current + 1);
  }, [fixJob.data]);

  if (scanQuery.isPending) return <EmptyState title="Scanning package security..." />;
  if (scanQuery.isError) {
    return <EmptyState title="Package security scan failed" body={scanQuery.error.message} />;
  }

  const summary = scanQuery.data.summary;

  return (
    <div className="security-workspace">
      <section className="security-command-center">
        <div>
          <span className="module-eyebrow select-none">Package security</span>
          <h1>Finding triage</h1>
          <p>{scanQuery.data.project}</p>
        </div>
        <div className="security-command-center__metrics">
          <Metric label="findings" value={String(summary.total)} variant="failed" />
          <Metric label="fixable" value={String(summary.fixable)} variant="update" />
          <Metric
            label="ecosystems"
            value={String(scanQuery.data.ecosystems.length)}
            variant="ok"
          />
          <Metric label={scanQuery.data.cached ? "cached" : "fresh"} value="scan" variant="stale" />
        </div>
      </section>

      <section className="security-filters">
        <div className="segmented-control">
          {severities.map((item) => (
            <button
              type="button"
              key={item}
              className={severity === item ? "is-active" : ""}
              onClick={() => setSeverity(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <select value={ecosystem} onChange={(event) => setEcosystem(event.target.value)}>
          {ecosystems.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <button
          type="button"
          className={fixableOnly ? "is-active" : ""}
          aria-pressed={fixableOnly}
          onClick={() => setFixableOnly((current) => !current)}
        >
          Fixable only
        </button>
        <button
          type="button"
          disabled={scanQuery.isFetching}
          onClick={() => setRefreshToken((current) => current + 1)}
        >
          {scanQuery.isFetching ? "Rescanning" : "Rescan"}
        </button>
      </section>

      {scanQuery.data.notices.length > 0 ? (
        <div className="security-notice-strip">
          {scanQuery.data.notices.map((notice) => (
            <span key={notice}>{notice}</span>
          ))}
        </div>
      ) : null}

      <section className="security-board">
        <div className="security-finding-stack">
          {visibleFindings.length === 0 ? (
            <EmptyState title="No findings matched" />
          ) : (
            visibleFindings.map((finding) => (
              <button
                type="button"
                key={finding.key}
                className={`security-finding-row${
                  selectedFinding?.key === finding.key ? " is-active" : ""
                }`}
                onClick={() => setSelectedKey(finding.key)}
              >
                <span>
                  <strong>{finding.package}</strong>
                  <small>
                    {finding.ecosystem} / {finding.kind} / {finding.current}
                  </small>
                </span>
                <span className="security-finding-row__upgrade">
                  <strong>{finding.target ?? "review"}</strong>
                  <small>{finding.fix_available ? "automated" : "manual"}</small>
                </span>
                <StatePill variant={severityVariant(finding.severity)} label={finding.severity} />
              </button>
            ))
          )}
        </div>

        <FindingInspector
          finding={selectedFinding}
          onFix={(finding) => fixAction.prepare({ finding_key: finding.key })}
          busy={fixAction.phase === "preparing" || fixAction.phase === "executing"}
        />
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

function Metric({
  label,
  value,
  variant,
}: {
  label: string;
  value: string;
  variant: StatePillVariant;
}) {
  return (
    <span>
      <strong>{value}</strong>
      <StatePill variant={variant} label={label} />
    </span>
  );
}

function FindingInspector({
  finding,
  onFix,
  busy,
}: {
  finding: SecurityFinding | null;
  onFix: (finding: SecurityFinding) => void;
  busy: boolean;
}) {
  if (finding === null) {
    return (
      <aside className="security-inspector">
        <EmptyState title="No finding selected" />
      </aside>
    );
  }

  return (
    <aside className="security-inspector">
      <span className="module-eyebrow select-none">{finding.ecosystem}</span>
      <h2>{finding.package}</h2>
      <div className="security-inspector__meta">
        <StatePill variant={severityVariant(finding.severity)} label={finding.severity} />
        <span>{finding.kind}</span>
        <span>
          {finding.current}
          {finding.target !== null ? ` -> ${finding.target}` : ""}
        </span>
      </div>
      <p>{finding.detail || "No detail supplied by the scanner."}</p>
      <div className="security-command-preview">
        <span>Fix command</span>
        <code>{finding.fix_command_preview || "No automated fix available"}</code>
      </div>
      <ol className="security-remediation-path" aria-label="Remediation path">
        <li className="is-complete">Finding</li>
        <li className={finding.fix_command_preview ? "is-complete" : ""}>Command review</li>
        <li className={finding.fix_available ? "is-ready" : ""}>Confirmed apply</li>
      </ol>
      <button
        type="button"
        disabled={!finding.fix_available || busy}
        onClick={() => onFix(finding)}
      >
        Apply fix
      </button>
    </aside>
  );
}

function severityVariant(severity: string): StatePillVariant {
  switch (severity.toLowerCase()) {
    case "critical":
    case "high":
      return "error";
    case "moderate":
    case "medium":
      return "degraded";
    case "low":
    case "info":
      return "ok";
    default:
      return "unavailable";
  }
}
