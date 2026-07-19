// Auto-scrolling monospace log pane fed by useEventStream events, with a gap indicator and follow toggle.
import { useEffect, useRef, useState } from "react";
import { StatePill } from "@/components/StatePill";
import { type StreamConnectionState, type StreamEvent, streamStateToPillVariant } from "@/lib/sse";

export interface LogStreamProps {
  events: StreamEvent[];
  connectionState: StreamConnectionState;
  autoFollow?: boolean;
}

export function LogStream({ events, connectionState, autoFollow = true }: LogStreamProps) {
  const [follow, setFollow] = useState(autoFollow);
  const containerRef = useRef<HTMLDivElement>(null);

  // biome-ignore lint/correctness/useExhaustiveDependencies: re-scroll whenever new events arrive, not read directly in the effect body
  useEffect(() => {
    if (!follow || containerRef.current === null) return;
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [events, follow]);

  const lines = events.filter((event) => event.event === "output");
  const gapCount = events
    .filter((event) => event.event === "gap")
    .reduce((total, event) => total + gapDroppedCount(event), 0);

  function handleScroll(): void {
    const container = containerRef.current;
    if (container === null || !follow) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceFromBottom > 16) setFollow(false);
  }

  return (
    <div className="log-stream">
      <div className="log-stream__toolbar select-none">
        <StatePill variant={streamStateToPillVariant(connectionState)} />
        <span className="log-stream__count">
          {lines.length} {lines.length === 1 ? "line" : "lines"}
        </span>
        {gapCount > 0 ? (
          <span className="log-stream__gap" role="status">
            {gapCount} {gapCount === 1 ? "line" : "lines"} dropped during reconnect
          </span>
        ) : null}
        <label className="log-stream__follow">
          <input
            type="checkbox"
            checked={follow}
            onChange={(event) => setFollow(event.target.checked)}
          />
          Follow
        </label>
      </div>
      <div
        ref={containerRef}
        className="log-stream__body"
        role="log"
        aria-label="Job output"
        aria-relevant="additions text"
        onScroll={handleScroll}
      >
        {lines.length === 0 ? (
          <p className="log-stream__empty">
            {connectionState === "open" ? "Waiting for output" : "No output received"}
          </p>
        ) : (
          lines.map((event, index) => (
            <div key={event.id ?? `output-${index}`} className="log-stream__line">
              {extractLogLine(event)}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function gapDroppedCount(event: StreamEvent): number {
  if (typeof event.data !== "object" || event.data === null) return 0;
  const dropped = (event.data as { dropped?: unknown }).dropped;
  return typeof dropped === "number" ? dropped : 0;
}

function extractLogLine(event: StreamEvent): string {
  if (typeof event.data !== "object" || event.data === null) return "";
  const line = (event.data as { line?: unknown }).line;
  return typeof line === "string" ? line : "";
}
