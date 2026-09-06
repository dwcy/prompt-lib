// Small status badge mapping a semantic state variant to a styling hook class for T024.
// Extended for 021-codegen-eval-modules T024/T026/T036: the four persisted codegen run outcomes
// (rejected/halted/environment), the no-run-record case (unknown), and the eval run state that
// existing job variants don't cover (interrupted).
export type StatePillVariant =
  | "ok"
  | "loading"
  | "degraded"
  | "failed"
  | "stale"
  | "unavailable"
  | "installed"
  | "missing"
  | "update"
  | "connecting"
  | "open"
  | "closed"
  | "error"
  | "queued"
  | "running"
  | "succeeded"
  | "cancelled"
  | "rejected"
  | "halted"
  | "environment"
  | "interrupted"
  | "unknown";

export interface StatePillProps {
  variant: StatePillVariant;
  label?: string;
}

export function StatePill({ variant, label }: StatePillProps) {
  return (
    <span className={`state-pill state-pill--${variant} select-none`}>
      {label ?? (variant === "ok" ? "OK" : variant)}
    </span>
  );
}
