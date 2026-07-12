// Small status badge mapping a semantic state variant to a styling hook class for T024.
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
  | "cancelled";

export interface StatePillProps {
  variant: StatePillVariant;
  label?: string;
}

export function StatePill({ variant, label }: StatePillProps) {
  return (
    <span className={`state-pill state-pill--${variant} select-none`} role="status">
      {label ?? variant}
    </span>
  );
}
