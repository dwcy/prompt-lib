// Persisted diagnostic evidence rendered as chronological console-ledger rows with per-source
// retry. The backend bounds this collection, so plain rows beat a virtualized generic table.
import type { DiagnosticEvent } from "@/api/schemas";
import { SEVERITY_LABELS } from "@/modules/diagnostics/severityLabels";

export interface DiagnosticsHistoryTableProps {
  events: DiagnosticEvent[];
  onRetry: (module: string) => void;
}

export function DiagnosticsHistoryTable({ events, onRetry }: DiagnosticsHistoryTableProps) {
  return (
    <ol className="diag-ledger" aria-label="Persisted diagnostic events">
      {events.map((event) => (
        <li key={event.id} className="diag-ledger__row" data-severity={event.severity}>
          <time className="diag-ledger__time" dateTime={event.occurred_at}>
            {formatOccurredAt(event.occurred_at)}
          </time>
          <span className="diag-ledger__sev" data-severity={event.severity}>
            {SEVERITY_LABELS[event.severity]}
          </span>
          <span className="diag-ledger__module">{event.module}</span>
          <span className="diag-ledger__message" title={`event #${event.id} — ${event.message}`}>
            {event.message}
          </span>
          <span className="diag-ledger__kind">{event.kind.replace("_", " ")}</span>
          <button
            type="button"
            className="diag-ledger__retry select-none"
            onClick={() => onRetry(event.module)}
            aria-label={`Retry ${event.module}`}
          >
            Retry
          </button>
        </li>
      ))}
    </ol>
  );
}

function formatOccurredAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
