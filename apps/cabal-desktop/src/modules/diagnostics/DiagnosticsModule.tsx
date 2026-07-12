// Diagnostics & Backend Health: persisted history with a severity filter, a live stream tail, and
// per-source retry (T035).
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

export function DiagnosticsModule() {
  const [severity, setSeverity] = useState<SeverityFilterValue>("all");
  const historyQuery = useDiagnosticsHistory(severity === "all" ? {} : { severity });
  const stream = useEventStream("/api/diagnostics/stream");
  const retrySource = useDiagnosticsRetry();

  return (
    <div className="diagnostics">
      <section className="diagnostics__section">
        <h2 className="diagnostics__section-title select-none">Live feed</h2>
        <DiagnosticsLiveTail events={stream.events} connectionState={stream.state} />
      </section>

      <section className="diagnostics__section">
        <h2 className="diagnostics__section-title select-none">History</h2>
        <SeverityFilter value={severity} onChange={setSeverity} />
        {historyQuery.isPending ? (
          <EmptyState title="Loading diagnostics history…" />
        ) : historyQuery.isError ? (
          <EmptyState
            title="Could not load diagnostics history"
            body={historyQuery.error.message}
          />
        ) : historyQuery.data.length === 0 ? (
          <EmptyState title="No diagnostics recorded" body="Nothing to show for this filter yet." />
        ) : (
          <DiagnosticsHistoryTable events={historyQuery.data} onRetry={retrySource} />
        )}
      </section>
    </div>
  );
}
