// Persisted diagnostic evidence rendered as a chronological incident ledger. The backend bounds
// this collection, so a semantic list is more useful than a virtualized generic table.
import type { DiagnosticEvent } from "@/api/schemas";
import { StatePill, type StatePillVariant } from "@/components/StatePill";

export interface DiagnosticsHistoryTableProps {
  events: DiagnosticEvent[];
  onRetry: (module: string) => void;
}

function severityVariant(severity: DiagnosticEvent["severity"]): StatePillVariant {
  if (severity === "error") return "error";
  if (severity === "warning") return "degraded";
  return "ok";
}

export function DiagnosticsHistoryTable({ events, onRetry }: DiagnosticsHistoryTableProps) {
  return (
    <ol className="diagnostics-incident-ledger" aria-label="Persisted diagnostic events">
      {events.map((event, index) => (
        <li key={event.id} data-severity={event.severity}>
          <div className="diagnostics-incident-ledger__sequence" aria-hidden="true">
            <span>{String(index + 1).padStart(2, "0")}</span>
            <i />
          </div>
          <article>
            <header>
              <StatePill variant={severityVariant(event.severity)} label={event.severity} />
              <strong>{event.module}</strong>
              <time dateTime={event.occurred_at}>{formatOccurredAt(event.occurred_at)}</time>
            </header>
            <p>{event.message}</p>
            <footer>
              <span>{event.kind.replace("_", " ")}</span>
              <code>event #{event.id}</code>
            </footer>
          </article>
          <button type="button" onClick={() => onRetry(event.module)}>
            Retry source
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
