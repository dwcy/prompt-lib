// Display labels and value kind for each metric key, in the subsystem's own reduction order
// (data-model.md A8). The frontend renders these numbers; it never computes them (SC-010).
import type { EvalsMetricKey } from "@/api/evals";

export type EvalsMetricValueKind = "percent" | "count" | "duration";

export const EVALS_METRIC_ORDER: EvalsMetricKey[] = [
  "task_pass_rate",
  "test_pass_rate",
  "build_success_rate",
  "unrequested_changes",
  "tool_calls",
  "tokens_total",
  "wall_seconds",
  "pairwise_win_rate",
];

export const EVALS_METRIC_LABELS: Record<EvalsMetricKey, string> = {
  task_pass_rate: "Task pass rate",
  test_pass_rate: "Test pass rate",
  build_success_rate: "Build success rate",
  unrequested_changes: "Unrequested changes",
  tool_calls: "Tool calls",
  tokens_total: "Tokens (total)",
  wall_seconds: "Wall time",
  pairwise_win_rate: "Pairwise win rate",
};

export const EVALS_METRIC_KINDS: Record<EvalsMetricKey, EvalsMetricValueKind> = {
  task_pass_rate: "percent",
  test_pass_rate: "percent",
  build_success_rate: "percent",
  unrequested_changes: "count",
  tool_calls: "count",
  tokens_total: "count",
  wall_seconds: "duration",
  pairwise_win_rate: "percent",
};
