// useEventStream: reconnecting fetch-based SSE hook with Last-Event-ID replay and heartbeat staleness.
import { useEffect, useRef, useState } from "react";
import type { StatePillVariant } from "@/components/StatePill";
import { openSseConnection } from "@/lib/sseConnection";
import type { ParsedSseFrame } from "@/lib/sseFrames";

export type StreamConnectionState = "connecting" | "open" | "stale" | "closed" | "error";

// Shared by every stream consumer's connection-status pill (LogStream, DiagnosticsLiveTail) so the
// state→variant mapping isn't duplicated per consumer.
export function streamStateToPillVariant(state: StreamConnectionState): StatePillVariant {
  return state;
}

export interface StreamEvent {
  event: string;
  id: number | null;
  data: unknown;
}

export interface UseEventStreamOptions {
  enabled?: boolean;
  maxEvents?: number;
}

export interface UseEventStreamResult {
  events: StreamEvent[];
  state: StreamConnectionState;
  lastSeq: number | null;
}

const RECONNECT_BASE_DELAY_MS = 500;
const RECONNECT_MAX_DELAY_MS = 8_000;
const HEARTBEAT_STALE_AFTER_MS = 30_000; // 2 missed heartbeats at the contract's <=15s cadence
const STALE_CHECK_INTERVAL_MS = 5_000;
const DEFAULT_MAX_EVENTS = 1_000;

const TERMINAL_JOB_STATES = new Set(["succeeded", "failed", "cancelled"]);

function isTerminalStateFrame(frame: ParsedSseFrame): boolean {
  if (frame.event !== "state" || typeof frame.data !== "object" || frame.data === null)
    return false;
  const state = (frame.data as { state?: unknown }).state;
  return typeof state === "string" && TERMINAL_JOB_STATES.has(state);
}

export function useEventStream(
  path: string,
  opts: UseEventStreamOptions = {},
): UseEventStreamResult {
  const { enabled = true, maxEvents = DEFAULT_MAX_EVENTS } = opts;
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [state, setState] = useState<StreamConnectionState>("connecting");
  const [lastSeq, setLastSeq] = useState<number | null>(null);
  const lastSeqRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const abortController = new AbortController();
    let cancelled = false;
    let lastActivity = Date.now();
    let attempt = 0;

    setState("connecting");
    setEvents([]);
    lastSeqRef.current = null;
    setLastSeq(null);

    const staleTimer = window.setInterval(() => {
      if (Date.now() - lastActivity >= HEARTBEAT_STALE_AFTER_MS) {
        setState((current) => (current === "open" ? "stale" : current));
      }
    }, STALE_CHECK_INTERVAL_MS);

    async function runConnection(): Promise<boolean> {
      let sawTerminal = false;
      try {
        for await (const frame of openSseConnection(
          path,
          lastSeqRef.current,
          abortController.signal,
        )) {
          lastActivity = Date.now();
          setState("open");
          if (frame.id !== null) {
            lastSeqRef.current = frame.id;
            setLastSeq(frame.id);
          }
          if (frame.event === "heartbeat") continue;
          setEvents((current) => {
            const incoming = { event: frame.event, id: frame.id, data: frame.data };
            // Every stream segment re-announces the same non-terminal state; left to
            // accumulate they fill the ring and evict the output lines the log pane renders.
            const last = current[current.length - 1];
            const repeatsState =
              incoming.event === "state" &&
              last?.event === "state" &&
              JSON.stringify(last.data) === JSON.stringify(incoming.data);
            const next = repeatsState
              ? [...current.slice(0, -1), incoming]
              : [...current, incoming];
            return next.length > maxEvents ? next.slice(next.length - maxEvents) : next;
          });
          if (isTerminalStateFrame(frame)) sawTerminal = true;
        }
      } catch (error) {
        if (abortController.signal.aborted) return true;
        throw error;
      }
      return sawTerminal;
    }

    async function loop(): Promise<void> {
      while (!cancelled) {
        setState((current) => (current === "open" ? current : "connecting"));
        try {
          const terminal = await runConnection();
          if (cancelled) return;
          if (terminal) {
            setState("closed");
            return;
          }
          attempt = 0; // clean segment close per the bounded job-stream contract — reconnect immediately
        } catch {
          if (cancelled) return;
          setState("error");
          attempt += 1;
          const delay = Math.min(RECONNECT_BASE_DELAY_MS * 2 ** attempt, RECONNECT_MAX_DELAY_MS);
          await new Promise((resolve) => window.setTimeout(resolve, delay));
        }
      }
    }

    void loop();

    return () => {
      cancelled = true;
      abortController.abort();
      window.clearInterval(staleTimer);
    };
  }, [path, enabled, maxEvents]);

  return { events, state, lastSeq };
}
