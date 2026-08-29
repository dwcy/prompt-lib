// T037: the A/B verdict for one completed eval run — per-metric baseline vs candidate, aggregated
// and per task, judge verdicts with honest exclusions, and a drill-down into any cell. Renders
// numbers exactly as the backend's reducer computed them (SC-010); computes nothing itself.
import { useState } from "react";
import { useEvalsReport } from "@/api/evals";
import { EmptyState } from "@/components/EmptyState";
import { CellDetail } from "@/modules/evals/components/CellDetail";
import { CellPicker } from "@/modules/evals/components/CellPicker";
import { MetricsTable } from "@/modules/evals/components/MetricsTable";
import { VerdictSummary } from "@/modules/evals/components/VerdictSummary";

export interface ComparisonViewProps {
  runId: string;
}

interface SelectedCell {
  task: string;
  profile: "baseline" | "candidate";
  repetition: number;
}

export function ComparisonView({ runId }: ComparisonViewProps) {
  const reportQuery = useEvalsReport(runId);
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null);

  if (reportQuery.isPending) return <EmptyState title="Loading comparison…" />;
  if (reportQuery.isError) {
    return (
      <EmptyState title="Could not load this run's comparison" body={reportQuery.error.message} />
    );
  }

  const report = reportQuery.data;

  return (
    <div className="comparison-view">
      <header className="comparison-view__header select-none">
        <h2>
          {report.baseline} vs {report.candidate}
        </h2>
      </header>

      {!report.judge_available ? (
        <p className="comparison-view__degraded-notice" role="status">
          Judge results are unavailable for this run — showing deterministic checks only.
        </p>
      ) : null}

      <section aria-label="Aggregate comparison">
        <h3>Aggregate (all tasks)</h3>
        <MetricsTable baseline={report.aggregate.baseline} candidate={report.aggregate.candidate} />
        <p className="comparison-view__failed-cells">
          {report.failed_cells} cell{report.failed_cells === 1 ? "" : "s"} failed outright — counted
          against the task pass rate above and excluded from the quality means.
        </p>
      </section>

      {report.judge_available ? (
        <VerdictSummary verdicts={report.verdicts} excluded={report.pairwise_excluded} />
      ) : null}

      <section aria-label="Per-task comparison">
        <h3>Per task</h3>
        {report.per_task.map((task) => (
          <div key={task.task} className="comparison-view__task">
            <h4>{task.task}</h4>
            <MetricsTable baseline={task.metrics.baseline} candidate={task.metrics.candidate} />
            <CellPicker
              task={task.task}
              onView={(profile, repetition) =>
                setSelectedCell({ task: task.task, profile, repetition })
              }
            />
          </div>
        ))}
      </section>

      {selectedCell !== null ? (
        <CellDetail
          runId={runId}
          task={selectedCell.task}
          profile={selectedCell.profile === "baseline" ? report.baseline : report.candidate}
          repetition={selectedCell.repetition}
          onClose={() => setSelectedCell(null)}
        />
      ) : null}
    </div>
  );
}
