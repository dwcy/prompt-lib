// Baseline-vs-candidate figures for one metric set (aggregate or per-task). Every value carries
// its sample count (SC-009); spread renders only when the payload supplies it AND n >= 3 (FR-041)
// — a defensive re-check, not a trust override, since the backend already omits it below n=3.
import type { EvalsComparison, EvalsMetricAggregate, EvalsMetricKey } from "@/api/evals";
import { formatMetricMean, formatMetricSpread } from "@/modules/evals/evalsFormat";
import { EVALS_METRIC_LABELS, EVALS_METRIC_ORDER } from "@/modules/evals/evalsMetricLabels";

export interface MetricsTableProps {
  baseline: EvalsComparison["baseline"];
  candidate: EvalsComparison["candidate"];
}

export function MetricsTable({ baseline, candidate }: MetricsTableProps) {
  return (
    <table className="metrics-table">
      <thead>
        <tr>
          <th scope="col">Metric</th>
          <th scope="col">Baseline</th>
          <th scope="col">Candidate</th>
        </tr>
      </thead>
      <tbody>
        {EVALS_METRIC_ORDER.map((key) => (
          <tr key={key}>
            <th scope="row">{EVALS_METRIC_LABELS[key]}</th>
            <MetricCell metricKey={key} aggregate={baseline[key]} />
            <MetricCell metricKey={key} aggregate={candidate[key]} />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface MetricCellProps {
  metricKey: EvalsMetricKey;
  aggregate: EvalsMetricAggregate;
}

function MetricCell({ metricKey, aggregate }: MetricCellProps) {
  const showSpread = aggregate.stddev !== undefined && aggregate.n >= 3;
  return (
    <td>
      <span className="metrics-table__mean">{formatMetricMean(metricKey, aggregate.mean)}</span>
      {showSpread && aggregate.stddev !== undefined ? (
        <span className="metrics-table__spread">
          {formatMetricSpread(metricKey, aggregate.stddev)}
        </span>
      ) : null}
      <span className="metrics-table__n">n={aggregate.n}</span>
    </td>
  );
}
