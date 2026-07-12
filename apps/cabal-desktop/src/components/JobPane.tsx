// Job header + live state + LogStream + a cancel button gated behind an inline confirm.
import { useState } from "react";
import { useCancelJob, useJob } from "@/api/jobs";
import type { JobState } from "@/api/schemas";
import { LogStream } from "@/components/LogStream";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { type StreamEvent, useEventStream } from "@/lib/sse";

export interface JobPaneProps {
  jobId: string;
}

export function JobPane({ jobId }: JobPaneProps) {
  const jobQuery = useJob(jobId);
  const cancelJob = useCancelJob();
  const stream = useEventStream(`/api/jobs/${jobId}/stream`);
  const [confirmingCancel, setConfirmingCancel] = useState(false);

  const latestState = latestJobState(stream.events) ?? jobQuery.data?.state ?? "queued";
  const isCancellable = latestState === "queued" || latestState === "running";

  function handleCancelConfirmed(): void {
    setConfirmingCancel(false);
    cancelJob.mutate(jobId);
  }

  return (
    <section className="job-pane">
      <header className="job-pane__header select-none">
        <h3 className="job-pane__kind">{jobQuery.data?.kind ?? jobId}</h3>
        <StatePill variant={jobStateToVariant(latestState)} />
        {isCancellable ? (
          confirmingCancel ? (
            <span className="job-pane__cancel-confirm">
              Cancel this job?
              <button type="button" onClick={handleCancelConfirmed}>
                Yes, cancel
              </button>
              <button type="button" onClick={() => setConfirmingCancel(false)}>
                No
              </button>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingCancel(true)}
              disabled={cancelJob.isPending}
            >
              Cancel
            </button>
          )
        ) : null}
      </header>
      <LogStream events={stream.events} connectionState={stream.state} />
    </section>
  );
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
