// Diagnostics console: stat-card row, live collector log tail, and the persisted incident
// ledger with severity filtering and per-source retry (T035).
import { useState } from "react";
import { useDiagnosticsHistory } from "@/api/diagnostics";
import { EmptyState } from "@/components/EmptyState";
import { useEventStream } from "@/lib/sse";
import { DiagnosticsHistoryTable } from "@/modules/diagnostics/components/DiagnosticsHistoryTable";
import { DiagnosticsLiveTail } from "@/modules/diagnostics/components/DiagnosticsLiveTail";
import {
  SeverityFilter,
  type SeverityFilterValue,
} from "@/modules/diagnostics/components/SeverityFilter";
import { useDiagnosticsRetry } from "@/modules/diagnostics/hooks/useDiagnosticsRetry";
import "./DiagnosticsModule.css";

const HISTORY_LIMIT = 200;

export function DiagnosticsModule() {
  const [severity, setSeverity] = useState<SeverityFilterValue>("all");
  const allHistoryQuery = useDiagnosticsHistory({ limit: HISTORY_LIMIT });
  const historyQuery = useDiagnosticsHistory(
    severity === "all" ? { limit: HISTORY_LIMIT } : { limit: HISTORY_LIMIT, severity },
  );
  const stream = useEventStream("/api/diagnostics/stream");
  const retrySource = useDiagnosticsRetry();
  const events = allHistoryQuery.data ?? [];
  const errors = events.filter((event) => event.severity === "error").length;
  const warnings = events.filter((event) => event.severity === "warning").length;
  const history = historyQuery.data ?? [];
  const countsPending = allHistoryQuery.isPending;

  return (
    <div className="diag-module">
      <section className="diag-stats" aria-label="Diagnostic totals">
        <article className="diag-stat">
          <span className="diag-stat__label select-none">Events retained</span>
          <strong className="diag-stat__value">{countsPending ? "..." : events.length}</strong>
        </article>
        <article className="diag-stat diag-stat--danger">
          <span className="diag-stat__label select-none">Errors</span>
          <strong className="diag-stat__value">{countsPending ? "..." : errors}</strong>
        </article>
        <article className="diag-stat diag-stat--warning">
          <span className="diag-stat__label select-none">Warnings</span>
          <strong className="diag-stat__value">{countsPending ? "..." : warnings}</strong>
        </article>
        <article className="diag-stat">
          <span className="diag-stat__label select-none">Live stream</span>
          <strong className="diag-stat__value" data-stream-state={stream.state}>
            {stream.state}
          </strong>
        </article>
      </section>

      <DiagnosticsLiveTail events={stream.events} connectionState={stream.state} />

      <section className="diag-ledger-card" aria-labelledby="diag-ledger-title">
        <header className="diag-ledger-card__header select-none">
          <h2 id="diag-ledger-title">Incident ledger</h2>
          <span className="diag-ledger-card__count">{history.length} records</span>
          <div className="diag-ledger-card__filter">
            <SeverityFilter value={severity} onChange={setSeverity} />
          </div>
        </header>
        <div className="diag-ledger-card__body">
          {historyQuery.isPending ? (
            <div className="diag-ledger-card__state">
              <EmptyState title="Loading diagnostics history..." />
            </div>
          ) : historyQuery.isError ? (
            <div className="diag-ledger-card__state">
              <EmptyState
                title="Could not load diagnostics history"
                body={historyQuery.error.message}
              />
            </div>
          ) : history.length === 0 ? (
            <div className="diag-ledger-card__state">
              <EmptyState
                title="No matching evidence"
                body="Change the severity lens to widen the incident ledger."
              />
            </div>
          ) : (
            <DiagnosticsHistoryTable events={history} onRetry={retrySource} />
          )}
        </div>
      </section>
    </div>
  );
}
