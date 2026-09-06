// Collector log: live diagnostics tail rendered as a bottom-anchored console feed of
// DiagnosticEvent frames from /api/diagnostics/stream. Distinct from LogStream (built for
// plain-text job output) — diagnostics frames carry a full DiagnosticEvent object under
// `event: "diagnostic"`, not a `{ line }` payload.
import type { DiagnosticEvent } from "@/api/schemas";
import type { StreamConnectionState, StreamEvent } from "@/lib/sse";
import { SEVERITY_LABELS } from "@/modules/diagnostics/severityLabels";

export interface DiagnosticsLiveTailProps {
  events: StreamEvent[];
  connectionState: StreamConnectionState;
}

const STREAM_PATH = "/api/diagnostics/stream";

const TAIL_LABELS: Record<StreamConnectionState, string> = {
  open: "live tail",
  connecting: "connecting",
  stale: "stale feed",
  error: "reconnecting",
  closed: "stream closed",
};

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

export function DiagnosticsLiveTail({ events, connectionState }: DiagnosticsLiveTailProps) {
  const diagnostics = events
    .map(extractDiagnostic)
    .filter((event): event is DiagnosticEvent => event !== null);
  const live = connectionState === "open";

  return (
    <section className="diag-log" aria-label="Collector log">
      <header className="diag-log__header select-none">
        <b className="diag-log__title">Collector log</b>
        <span className="diag-log__tail" data-stream-state={connectionState} role="status">
          {live ? <i className="diag-log__dot" aria-hidden="true" /> : null}
          {TAIL_LABELS[connectionState]}
        </span>
        <code className="diag-log__source">{STREAM_PATH}</code>
      </header>
      <div className="diag-log__body">
        <ol className="diag-log__lines" aria-label="Live diagnostic events">
          {diagnostics.length === 0 ? (
            <li className="diag-log__empty">Waiting for the next backend signal.</li>
          ) : (
            diagnostics.map((event) => (
              <li key={event.id} className="diag-log__line">
                <time className="diag-log__time" dateTime={event.occurred_at}>
                  {formatSignalTime(event.occurred_at)}
                </time>
                <span className="diag-log__sev" data-severity={event.severity}>
                  {SEVERITY_LABELS[event.severity]}
                </span>
                <span className="diag-log__section">{event.module}</span>
                <span className="diag-log__message" title={event.message}>
                  {event.message}
                </span>
              </li>
            ))
          )}
        </ol>
      </div>
    </section>
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
