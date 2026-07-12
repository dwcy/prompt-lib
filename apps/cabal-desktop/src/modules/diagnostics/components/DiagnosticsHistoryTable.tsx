// Persisted diagnostics history with a per-row "retry this source" action. A plain semantic table,
// not VirtualDataTable: the backend already bounds this list via GET /api/diagnostics?limit=, so
// there's no confirmed large-N case to justify virtualization (which also can't be exercised under
// jsdom — @tanstack/react-virtual measures a real scroll container, which jsdom always reports as
// zero-sized).
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
    <table className="diagnostics-history-table">
      <thead>
        <tr>
          <th scope="col">Severity</th>
          <th scope="col">Module</th>
          <th scope="col">Message</th>
          <th scope="col">Occurred</th>
          <th scope="col">Kind</th>
          <th scope="col">
            <span className="select-none">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {events.map((event) => (
          <tr key={event.id}>
            <td>
              <StatePill variant={severityVariant(event.severity)} label={event.severity} />
            </td>
            <td>{event.module}</td>
            <td>{event.message}</td>
            <td>{new Date(event.occurred_at).toLocaleString()}</td>
            <td>{event.kind}</td>
            <td>
              <button type="button" onClick={() => onRetry(event.module)}>
                Retry
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
