// KPI stat card: label + delta chip, large value with unit, sparkline, hint (console redesign).
import type { ReactNode } from "react";

export type KpiDeltaTone = "ok" | "info" | "warning" | "danger" | "neutral";

export interface KpiCardProps {
  label: string;
  value: string;
  unit?: string;
  delta?: string;
  deltaTone?: KpiDeltaTone;
  hint?: string;
  /** Optional slot rendered beside the value. */
  aside?: ReactNode;
}

export function KpiCard({
  label,
  value,
  unit,
  delta,
  deltaTone = "neutral",
  hint,
  aside,
}: KpiCardProps) {
  return (
    <div className="kpi-card">
      <div className="kpi-card__top">
        <span className="kpi-card__label">{label}</span>
        {delta ? (
          <span className={`kpi-card__delta kpi-card__delta--${deltaTone}`}>{delta}</span>
        ) : null}
      </div>
      <div className="kpi-card__row">
        <span className="kpi-card__value">
          {value}
          {unit ? <span className="kpi-card__unit"> {unit}</span> : null}
        </span>
        <span className="kpi-card__aside">{aside}</span>
      </div>
      {hint ? <div className="kpi-card__hint">{hint}</div> : null}
    </div>
  );
}
