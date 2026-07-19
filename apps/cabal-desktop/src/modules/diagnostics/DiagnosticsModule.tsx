// Diagnostics & Backend Health: source-ranked triage, persisted evidence, live telemetry, and
// per-source retry (T035).
import { useMemo, useState } from "react";
import { useDiagnosticsHistory } from "@/api/diagnostics";
import { useHealth } from "@/api/health";
import type { DiagnosticEvent, ModuleHealth } from "@/api/schemas";
import { EmptyState } from "@/components/EmptyState";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { useEventStream } from "@/lib/sse";
import { DiagnosticsHistoryTable } from "@/modules/diagnostics/components/DiagnosticsHistoryTable";
import { DiagnosticsLiveTail } from "@/modules/diagnostics/components/DiagnosticsLiveTail";
import {
  SeverityFilter,
  type SeverityFilterValue,
} from "@/modules/diagnostics/components/SeverityFilter";
import { useDiagnosticsRetry } from "@/modules/diagnostics/hooks/useDiagnosticsRetry";

type SourceSelection = "all" | string;

interface SourceSummary {
  source: string;
  total: number;
  errors: number;
  warnings: number;
  severity: DiagnosticEvent["severity"];
  latest: DiagnosticEvent;
  kinds: DiagnosticEvent["kind"][];
  health: ModuleHealth | null;
}

export function DiagnosticsModule() {
  const [severity, setSeverity] = useState<SeverityFilterValue>("all");
  const [selectedSource, setSelectedSource] = useState<SourceSelection>("all");
  const allHistoryQuery = useDiagnosticsHistory({ limit: 200 });
  const historyQuery = useDiagnosticsHistory(
    severity === "all" ? { limit: 200 } : { limit: 200, severity },
  );
  const healthQuery = useHealth();
  const stream = useEventStream("/api/diagnostics/stream");
  const retrySource = useDiagnosticsRetry();
  const events = allHistoryQuery.data ?? [];
  const errors = events.filter((event) => event.severity === "error").length;
  const warnings = events.filter((event) => event.severity === "warning").length;
  const sourceSummaries = useMemo(
    () => buildSourceSummaries(events, healthQuery.data?.modules ?? []),
    [events, healthQuery.data?.modules],
  );
  const selectedSummary =
    selectedSource === "all"
      ? (sourceSummaries[0] ?? null)
      : (sourceSummaries.find((source) => source.source === selectedSource) ??
        sourceSummaries[0] ??
        null);
  const visibleHistory = (historyQuery.data ?? []).filter(
    (event) => selectedSource === "all" || event.module === selectedSource,
  );
  const maxSourceCount = sourceSummaries[0]?.total ?? 1;
  const health = errors > 0 ? "disrupted" : warnings > 0 ? "attention" : "clear";
  const evidenceLabel = selectedSource === "all" ? "all sources" : selectedSource;

  return (
    <div className="diagnostics">
      <section className="diagnostics-command-center">
        <div>
          <span className="us3-eyebrow">Backend signal room</span>
          <h1>Diagnostics</h1>
          <p>Find the pressure point, inspect its evidence, then retry the affected source.</p>
        </div>
        <section className="diagnostics-command-center__metrics" aria-label="Diagnostic totals">
          <span data-tone={errors > 0 ? "error" : "neutral"}>
            <strong>{errors}</strong>
            <small>errors</small>
          </span>
          <span data-tone={warnings > 0 ? "warning" : "neutral"}>
            <strong>{warnings}</strong>
            <small>warnings</small>
          </span>
          <span>
            <strong>{sourceSummaries.length}</strong>
            <small>affected</small>
          </span>
          <span>
            <strong>
              {healthQuery.data === undefined ? "..." : `v${healthQuery.data.version}`}
            </strong>
            <small>backend</small>
          </span>
        </section>
        <div className="diagnostics-command-center__state">
          <StatePill variant={healthVariant(health)} label={health} />
          <small>{stream.state} telemetry</small>
        </div>
      </section>

      <section className="diagnostics-triage" aria-labelledby="diagnostics-triage-title">
        <header className="diagnostics-triage__header">
          <div>
            <span className="us3-eyebrow">Incident pressure map</span>
            <h2 id="diagnostics-triage-title">Affected sources</h2>
          </div>
          <button
            type="button"
            className={selectedSource === "all" ? "is-active" : ""}
            onClick={() => setSelectedSource("all")}
          >
            All evidence <strong>{events.length}</strong>
          </button>
        </header>

        {sourceSummaries.length === 0 ? (
          <div className="diagnostics-triage__clear">
            <StatePill variant="ok" label="clear" />
            <div>
              <strong>No persisted incident pressure</strong>
              <span>Live telemetry remains connected below for new backend signals.</span>
            </div>
          </div>
        ) : (
          <div className="diagnostics-triage__body">
            <nav className="diagnostics-source-map" aria-label="Affected diagnostic sources">
              {sourceSummaries.map((source, index) => (
                <button
                  type="button"
                  key={source.source}
                  className={selectedSource === source.source ? "is-active" : ""}
                  data-severity={source.severity}
                  onClick={() => setSelectedSource(source.source)}
                >
                  <span className="diagnostics-source-map__rank">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="diagnostics-source-map__identity">
                    <strong>{source.source}</strong>
                    <small>
                      {source.total} signals / last {formatRelativeTime(source.latest.occurred_at)}
                    </small>
                  </span>
                  <span className="diagnostics-source-map__count">{source.total}</span>
                  <span className="diagnostics-source-map__meter" aria-hidden="true">
                    <i
                      style={{ width: `${Math.max(8, (source.total / maxSourceCount) * 100)}%` }}
                    />
                  </span>
                </button>
              ))}
            </nav>

            {selectedSummary !== null && (
              <article
                className="diagnostics-recovery-brief"
                data-severity={selectedSummary.severity}
              >
                <header>
                  <div>
                    <span className="us3-eyebrow">
                      {selectedSource === "all" ? "Highest pressure" : "Selected source"}
                    </span>
                    <h3>{selectedSummary.source}</h3>
                  </div>
                  <StatePill
                    variant={severityVariant(selectedSummary.severity)}
                    label={selectedSummary.severity}
                  />
                </header>

                <p className="diagnostics-recovery-brief__message">
                  Latest signal: {selectedSummary.latest.message}
                </p>

                <dl className="diagnostics-recovery-brief__facts">
                  <div>
                    <dt>Recurrence</dt>
                    <dd>{selectedSummary.total} signals</dd>
                  </div>
                  <div>
                    <dt>Errors</dt>
                    <dd>{selectedSummary.errors}</dd>
                  </div>
                  <div>
                    <dt>Warnings</dt>
                    <dd>{selectedSummary.warnings}</dd>
                  </div>
                  <div>
                    <dt>Last seen</dt>
                    <dd>{formatRelativeTime(selectedSummary.latest.occurred_at)}</dd>
                  </div>
                </dl>

                <div className="diagnostics-recovery-brief__context">
                  <div>
                    <span>Evidence classes</span>
                    <strong>{selectedSummary.kinds.map(formatKind).join(" / ")}</strong>
                  </div>
                  <div>
                    <span>Health probe</span>
                    <strong>{selectedSummary.health?.detail ?? "No matching health probe"}</strong>
                  </div>
                </div>

                <footer>
                  <span>
                    Retry invalidates the cached source and requests fresh evidence across this
                    workspace.
                  </span>
                  <button type="button" onClick={() => retrySource(selectedSummary.source)}>
                    Retry {selectedSummary.source}
                  </button>
                </footer>
              </article>
            )}
          </div>
        )}
      </section>

      <div className="diagnostics-evidence-grid">
        <section className="diagnostics__section diagnostics__section--live">
          <div className="diagnostics-evidence-header">
            <div>
              <span className="us3-eyebrow">Now</span>
              <h2 className="diagnostics__section-title select-none">Live evidence</h2>
            </div>
            <small>{evidenceLabel}</small>
          </div>
          <DiagnosticsLiveTail
            events={stream.events}
            connectionState={stream.state}
            module={selectedSource === "all" ? null : selectedSource}
          />
        </section>

        <section className="diagnostics__section diagnostics__section--history">
          <div className="diagnostics-history-header">
            <div>
              <span className="us3-eyebrow">Persisted evidence</span>
              <h2 className="diagnostics__section-title select-none">Incident ledger</h2>
            </div>
            <SeverityFilter value={severity} onChange={setSeverity} />
          </div>
          <div className="diagnostics-history-scope">
            <span>{evidenceLabel}</span>
            <strong>{visibleHistory.length} records</strong>
          </div>
          {historyQuery.isPending ? (
            <EmptyState title="Loading diagnostics history..." />
          ) : historyQuery.isError ? (
            <EmptyState
              title="Could not load diagnostics history"
              body={historyQuery.error.message}
            />
          ) : visibleHistory.length === 0 ? (
            <EmptyState
              title="No matching evidence"
              body="Change the source or severity lens to widen the incident ledger."
            />
          ) : (
            <DiagnosticsHistoryTable events={visibleHistory} onRetry={retrySource} />
          )}
        </section>
      </div>
    </div>
  );
}

function buildSourceSummaries(
  events: DiagnosticEvent[],
  moduleHealth: ModuleHealth[],
): SourceSummary[] {
  const groups = new Map<string, DiagnosticEvent[]>();
  for (const event of events) {
    const group = groups.get(event.module) ?? [];
    group.push(event);
    groups.set(event.module, group);
  }

  return Array.from(groups.entries())
    .map(([source, sourceEvents]) => {
      const sorted = [...sourceEvents].sort(
        (left, right) => Date.parse(right.occurred_at) - Date.parse(left.occurred_at),
      );
      const errors = sourceEvents.filter((event) => event.severity === "error").length;
      const warnings = sourceEvents.filter((event) => event.severity === "warning").length;
      return {
        source,
        total: sourceEvents.length,
        errors,
        warnings,
        severity: errors > 0 ? "error" : warnings > 0 ? "warning" : "info",
        latest: sorted[0],
        kinds: Array.from(new Set(sourceEvents.map((event) => event.kind))),
        health: moduleHealth.find((module) => module.module === source) ?? null,
      } satisfies SourceSummary;
    })
    .sort((left, right) => {
      const severityDelta = severityWeight(right.severity) - severityWeight(left.severity);
      if (severityDelta !== 0) return severityDelta;
      if (right.total !== left.total) return right.total - left.total;
      return Date.parse(right.latest.occurred_at) - Date.parse(left.latest.occurred_at);
    });
}

function severityWeight(severity: DiagnosticEvent["severity"]) {
  if (severity === "error") return 3;
  if (severity === "warning") return 2;
  return 1;
}

function severityVariant(severity: DiagnosticEvent["severity"]): StatePillVariant {
  if (severity === "error") return "error";
  if (severity === "warning") return "degraded";
  return "ok";
}

function healthVariant(health: "disrupted" | "attention" | "clear"): StatePillVariant {
  if (health === "disrupted") return "error";
  if (health === "attention") return "degraded";
  return "ok";
}

function formatKind(kind: DiagnosticEvent["kind"]) {
  return kind.replace("_", " ");
}

function formatRelativeTime(value: string) {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  const elapsedSeconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (elapsedSeconds < 60) return "just now";
  const minutes = Math.floor(elapsedSeconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
