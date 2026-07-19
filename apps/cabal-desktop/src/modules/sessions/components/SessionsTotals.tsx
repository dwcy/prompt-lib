// Totals row: five KPI stat cards computed from the sessions totals payload.
import type { SessionTotals } from "@/api/observability";
import { KpiCard } from "@/components/KpiCard";
import {
  formatCount,
  formatMoney,
  formatTokens,
  formatWallHours,
} from "../sessionsPresentation";

export interface SessionsTotalsProps {
  totals: SessionTotals;
}

export function SessionsTotals({ totals }: SessionsTotalsProps) {
  const totalTokens = totals.tokens_in + totals.tokens_out;
  return (
    <div className="sess-totals">
      <KpiCard label="Sessions" value={formatCount(totals.session_count)} />
      <KpiCard label="Total cost" value={formatMoney(totals.cost_usd)} />
      <KpiCard label="Wall time" value={formatWallHours(totals.duration_seconds)} unit="h" />
      <KpiCard
        label="Tokens"
        value={formatTokens(totalTokens)}
        hint={`${formatTokens(totals.tokens_in)} in · ${formatTokens(totals.tokens_out)} out · ${formatTokens(totals.cache_read_tokens)} cache read`}
      />
      <KpiCard label="Subagent dispatches" value={formatCount(totals.agent_count)} />
    </div>
  );
}
