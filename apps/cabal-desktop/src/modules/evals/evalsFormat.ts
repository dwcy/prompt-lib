// Pure display formatting for evals metric values — unit conversion only, never a new statistic.
// Aggregation (mean, stddev, win rate, pass rate) lives entirely in the backend's reducer.
import type { EvalsMetricKey } from "@/api/evals";
import { EVALS_METRIC_KINDS, type EvalsMetricValueKind } from "@/modules/evals/evalsMetricLabels";

export function formatMetricMean(key: EvalsMetricKey, mean: number | null): string {
  if (mean === null) return "no samples";
  return formatByKind(EVALS_METRIC_KINDS[key], mean);
}

export function formatMetricSpread(key: EvalsMetricKey, stddev: number): string {
  return `± ${formatByKind(EVALS_METRIC_KINDS[key], stddev)}`;
}

function formatByKind(kind: EvalsMetricValueKind, value: number): string {
  switch (kind) {
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "duration":
      return `${value.toFixed(1)}s`;
    case "count":
      return value.toFixed(2).replace(/\.00$/, "");
  }
}
