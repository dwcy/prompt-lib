// T036: agent eval harness module shell — the availability gate (FR-002, distinguishing
// no_project_selected/subsystem_missing which block the module from the definition-tree reasons
// which only affect launching and authoring), run history newest-first, and the selected run's
// comparison. FR-045: this list includes runs the CLI produced, not only ones launched here.
import { useState } from "react";
import type { EvalsAvailabilityReason, EvalsRunState } from "@/api/evals";
import { useEvalsAvailability, useEvalsRuns } from "@/api/evals";
import { EmptyState } from "@/components/EmptyState";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import { ComparisonView } from "@/modules/evals/components/ComparisonView";

const AVAILABILITY_COPY: Partial<Record<EvalsAvailabilityReason, { title: string; body: string }>> =
  {
    no_project_selected: {
      title: "Select a project first",
      body: "The eval harness works against the selected project's benchmark tree.",
    },
    subsystem_missing: {
      title: "Eval harness unavailable",
      body: "The cabal.evals CLI or its dependencies could not be found.",
    },
  };

// Only these reasons mean nothing in the module can be shown. The definition-tree reasons
// (no_benchmark_tree, definitions_invalid, definitions_read_only) gate launching (US3/US5) and
// authoring (US6) only — they must not hide runs the CLI already produced (FR-045, US2).
const BLOCKING_REASONS = new Set<EvalsAvailabilityReason>([
  "no_project_selected",
  "subsystem_missing",
]);

const RUN_STATE_VARIANT: Record<EvalsRunState, StatePillVariant> = {
  running: "running",
  succeeded: "succeeded",
  failed: "failed",
  interrupted: "interrupted",
  cancelled: "cancelled",
};

export function EvalsModule() {
  const { navigateToModule } = useModuleNavigation();
  const availability = useEvalsAvailability();
  const runsQuery = useEvalsRuns();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  if (availability.isPending) return <EmptyState title="Checking eval harness availability…" />;
  if (availability.isError) {
    return (
      <EmptyState title="Could not reach the eval harness" body={availability.error.message} />
    );
  }

  if (!availability.data.available && BLOCKING_REASONS.has(availability.data.reason)) {
    const copy = AVAILABILITY_COPY[availability.data.reason] ?? {
      title: "Eval harness unavailable",
      body: availability.data.detail,
    };
    return (
      <EmptyState
        title={copy.title}
        body={availability.data.detail || copy.body}
        action={
          availability.data.reason === "no_project_selected" ? (
            <button type="button" onClick={() => navigateToModule("project_gate")}>
              Choose a project
            </button>
          ) : undefined
        }
      />
    );
  }

  const definitionNotice =
    availability.data.reason === "no_benchmark_tree" ||
    availability.data.reason === "definitions_invalid" ||
    availability.data.reason === "definitions_read_only"
      ? availability.data.detail
      : null;

  if (runsQuery.isPending) return <EmptyState title="Loading eval runs…" />;
  if (runsQuery.isError) {
    return <EmptyState title="Could not load eval runs" body={runsQuery.error.message} />;
  }

  return (
    <div className="evals-module">
      <header className="evals-module__header">
        <h1>Agent Eval Harness</h1>
        <p>Baseline-vs-candidate matrix runs, judged and reduced by the harness's own reducer.</p>
      </header>

      {definitionNotice !== null ? (
        <p className="evals-module__definition-notice" role="status">
          {definitionNotice}
        </p>
      ) : null}

      {runsQuery.data.length === 0 ? (
        <EmptyState
          title="No eval runs yet"
          body="Runs produced by the CLI or launched from this workspace both appear here."
        />
      ) : (
        <ul className="evals-module__run-list" aria-label="Eval run history">
          {runsQuery.data.map((run) => (
            <li key={run.run_id}>
              {run.readable ? (
                <button
                  type="button"
                  className="evals-module__run-row"
                  aria-current={selectedRunId === run.run_id}
                  onClick={() => setSelectedRunId(run.run_id)}
                >
                  <StatePill variant={RUN_STATE_VARIANT[run.state]} />
                  <span>
                    {run.baseline} vs {run.candidate}
                  </span>
                  <span>{run.created_at}</span>
                  {run.state === "interrupted" && run.resumable ? (
                    <span className="evals-module__resumable-flag">resumable</span>
                  ) : null}
                </button>
              ) : (
                <p className="evals-module__run-error" role="alert">
                  {run.run_id}: {run.error}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {selectedRunId !== null ? <ComparisonView runId={selectedRunId} /> : null}
    </div>
  );
}
