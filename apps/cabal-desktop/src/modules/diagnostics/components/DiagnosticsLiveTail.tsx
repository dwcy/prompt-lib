// Live diagnostics tail: structured DiagnosticEvent rows from the /api/diagnostics/stream SSE feed.
// Distinct from LogStream (built for plain-text job output) — diagnostics frames carry a full
// DiagnosticEvent object under `event: "diagnostic"`, not a `{ line }` payload.
import type { DiagnosticEvent } from "@/api/schemas";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { type StreamConnectionState, type StreamEvent, streamStateToPillVariant } from "@/lib/sse";

export interface DiagnosticsLiveTailProps {
  events: StreamEvent[];
  connectionState: StreamConnectionState;
  module?: string | null;
}

function severityVariant(severity: string): StatePillVariant {
  if (severity === "error") return "error";
  if (severity === "warning") return "degraded";
  return "ok";
}

function extractDiagnostic(event: StreamEvent): DiagnosticEvent | null {
  if (event.event !== "diagnostic" || typeof event.data !== "object" || event.data === null) {
    return null;
  }
  const candidate = event.data as Partial<DiagnosticEvent>;
  if (
    typeof candidate.id !== "number" ||
    typeof candidate.severity !== "string" ||
    typeof candidate.module !== "string" ||
    typeof candidate.message !== "string" ||
    typeof candidate.occurred_at !== "string" ||
    typeof candidate.kind !== "string"
  ) {
    return null;
  }
  return candidate as DiagnosticEvent;
}

export function DiagnosticsLiveTail({
  events,
  connectionState,
  module = null,
}: DiagnosticsLiveTailProps) {
  const diagnostics = events
    .map(extractDiagnostic)
    .filter((event): event is DiagnosticEvent => event !== null)
    .filter((event) => module === null || event.module === module);

  return (
    <div className="diagnostics-live-tail">
      <div className="diagnostics-live-tail__toolbar select-none">
        <StatePill variant={streamStateToPillVariant(connectionState)} />
        <span>{module === null ? "All source traffic" : `${module} traffic`}</span>
      </div>
      <ul className="diagnostics-live-tail__body" aria-label="Live diagnostic events">
        {diagnostics.length === 0 ? (
          <li className="diagnostics-live-tail__empty">Waiting for the next backend signal.</li>
        ) : (
          diagnostics.map((event) => (
            <li key={event.id} className="diagnostics-live-tail__row">
              <StatePill variant={severityVariant(event.severity)} label={event.severity} />
              <span className="diagnostics-live-tail__module">{event.module}</span>
              <span className="diagnostics-live-tail__message">{event.message}</span>
              <time dateTime={event.occurred_at}>{formatSignalTime(event.occurred_at)}</time>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

function formatSignalTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
