// Totals row: five KPI stat cards computed from the sessions totals payload.
import type { SessionTotals } from "@/api/observability";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { KpiCard } from "@/components/KpiCard";
import { RefreshButton } from "@/components/RefreshButton";
import {
  formatCount,
  formatMoney,
  formatTokens,
  formatWallHours,
  pricingHint,
} from "../sessionsPresentation";

export interface SessionsTotalsProps {
  totals: SessionTotals;
  onRefresh: () => void;
  isFetching: boolean;
}

export function SessionsTotals({ totals, onRefresh, isFetching }: SessionsTotalsProps) {
  const totalTokens = totals.tokens_in + totals.tokens_out;
  const unpriced = totals.unpriced_models;
  return (
    <div className="sess-totals">
      <KpiCard label="Sessions" value={formatCount(totals.session_count)} />
      <KpiCard
        label="Total cost"
        value={formatMoney(totals.cost_usd)}
        // An unpriced model spends tokens but contributes no dollars, so the total is a
        // floor. Say so on the card — a silently understated figure reads as a cheap month.
        delta={unpriced.length > 0 ? "incomplete" : undefined}
        deltaTone="warning"
        hint={pricingHint(unpriced, totals.pricing_as_of)}
      />
      <KpiCard label="Wall time" value={formatWallHours(totals.duration_seconds)} unit="h" />
      <KpiCard
        label="Tokens"
        value={formatTokens(totalTokens)}
        hint={`${formatTokens(totals.tokens_in)} in · ${formatTokens(totals.tokens_out)} out · ${formatTokens(totals.cache_read_tokens)} cache read`}
      />
      <KpiCard label="Subagent dispatches" value={formatCount(totals.agent_count)} />
      <CardRefreshFooter>
        <RefreshButton label="sessions" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </div>
  );
}
