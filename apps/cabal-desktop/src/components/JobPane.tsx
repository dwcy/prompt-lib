// Job header + live state + LogStream + a prepare/execute-gated cancel action.
import { useJob } from "@/api/jobs";
import type { JobState } from "@/api/schemas";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { LogStream } from "@/components/LogStream";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import { type StreamEvent, useEventStream } from "@/lib/sse";

export interface JobPaneProps {
  jobId: string;
  onDismiss?: () => void;
}

export function JobPane({ jobId, onDismiss }: JobPaneProps) {
  const jobQuery = useJob(jobId);
  const cancelJob = useAction("jobs.cancel");
  const stream = useEventStream(`/api/jobs/${jobId}/stream`);

  const latestState = latestJobState(stream.events) ?? jobQuery.data?.state ?? "queued";
  const isCancellable = latestState === "queued" || latestState === "running";
  const isTerminal =
    latestState === "succeeded" || latestState === "failed" || latestState === "cancelled";
  const jobKind = jobQuery.data?.kind;
  const job = jobQuery.data;

  return (
    <>
      <section className="job-pane">
        <header className="job-pane__header select-none">
          <div className="job-pane__identity">
            <h3 className="job-pane__kind">
              {jobKind === undefined ? "Background job" : formatJobKind(jobKind)}
            </h3>
            <code className="job-pane__id" title={jobId}>
              {jobId}
            </code>
          </div>
          <div className="job-pane__state" aria-live="polite">
            <StatePill variant={jobStateToVariant(latestState)} />
            <span>{JOB_STATE_COPY[latestState]}</span>
          </div>
          {isCancellable ? (
            <button
              type="button"
              className="job-pane__cancel"
              onClick={() => cancelJob.prepare({ job_id: jobId })}
              disabled={cancelJob.phase === "preparing" || cancelJob.phase === "executing"}
            >
              Cancel job
            </button>
          ) : null}
          {isTerminal && onDismiss !== undefined ? (
            <button
              type="button"
              className="job-pane__dismiss"
              onClick={onDismiss}
              aria-label="Dismiss job"
              title="Dismiss job"
            >
              <span aria-hidden="true">×</span>
            </button>
          ) : null}
        </header>
        <div className="job-pane__runway">
          <JobLifecycle state={latestState} />
          <dl className="job-pane__timing">
            <div>
              <dt>Created</dt>
              <dd>{formatJobTime(job?.created_at)}</dd>
            </div>
            <div>
              <dt>Started</dt>
              <dd>{formatJobTime(job?.started_at)}</dd>
            </div>
            <div>
              <dt>Elapsed</dt>
              <dd>{formatJobDuration(job?.started_at, job?.finished_at)}</dd>
            </div>
          </dl>
        </div>
        {job?.exit_detail ? (
          <p className="job-pane__exit-detail" data-state={latestState}>
            {job.exit_detail}
          </p>
        ) : null}
        <LogStream events={stream.events} connectionState={stream.state} />
      </section>
      <ConfirmDialog action={cancelJob} actionTitle="Cancel job" />
    </>
  );
}

function JobLifecycle({ state }: { state: JobState }) {
  const reachedRunning = state !== "queued";
  const reachedTerminal = state === "succeeded" || state === "failed" || state === "cancelled";
  const terminalLabel =
    state === "failed" ? "Failed" : state === "cancelled" ? "Cancelled" : "Complete";
  return (
    <ol className="job-pane__lifecycle" aria-label="Job lifecycle">
      <li className={reachedRunning ? "is-complete" : "is-current"}>
        <span>01</span>
        <strong>Queued</strong>
      </li>
      <li className={reachedTerminal ? "is-complete" : reachedRunning ? "is-current" : undefined}>
        <span>02</span>
        <strong>Running</strong>
      </li>
      <li className={reachedTerminal ? "is-current" : undefined} data-state={state}>
        <span>03</span>
        <strong>{terminalLabel}</strong>
      </li>
    </ol>
  );
}

const JOB_STATE_COPY: Record<JobState, string> = {
  queued: "Waiting to start",
  running: "Work is in progress",
  succeeded: "Completed successfully",
  failed: "Stopped after an error",
  cancelled: "Cancelled before completion",
};

function formatJobKind(kind: string): string {
  const words = kind.replace(/[._-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function formatJobTime(value: string | null | undefined): string {
  if (!value) return "pending";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatJobDuration(
  startedAt: string | null | undefined,
  finishedAt: string | null | undefined,
): string {
  if (!startedAt) return "pending";
  const started = new Date(startedAt).getTime();
  const finished = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  if (Number.isNaN(started) || Number.isNaN(finished)) return "unknown";
  const seconds = Math.max(0, Math.round((finished - started) / 1_000));
  if (seconds < 60) return `${String(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes)}m ${String(seconds % 60)}s`;
}

function latestJobState(events: StreamEvent[]): JobState | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event.event !== "state" || typeof event.data !== "object" || event.data === null) continue;
    const state = (event.data as { state?: unknown }).state;
    if (typeof state === "string") return state as JobState;
  }
  return null;
}

function jobStateToVariant(state: JobState): StatePillVariant {
  switch (state) {
    case "queued":
      return "queued";
    case "running":
      return "running";
    case "succeeded":
      return "succeeded";
    case "failed":
      return "failed";
    case "cancelled":
      return "cancelled";
  }
}
