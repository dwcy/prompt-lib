// Claude stats card: session/spend/token/subagent tile grid from real session totals, with a
// shortcut into the full Sessions & cost module.
import type { SessionTotals } from "@/api/observability";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { RefreshButton } from "@/components/RefreshButton";
import { formatCompactNumber, formatCount, formatMoney } from "../claudeStatsFormat";

export interface ClaudeStatsCardProps {
  totals: SessionTotals;
  onOpenSessions: () => void;
  onRefresh: () => void;
  isFetching: boolean;
}

interface StatTile {
  label: string;
  value: string;
  suffix?: string;
}

export function ClaudeStatsCard({
  totals,
  onOpenSessions,
  onRefresh,
  isFetching,
}: ClaudeStatsCardProps) {
  const tiles: StatTile[] = [
    { label: "Sessions", value: formatCount(totals.session_count) },
    { label: "Spend", value: formatMoney(totals.cost_usd) },
    {
      label: "Tokens in / out",
      value: formatCompactNumber(totals.tokens_in),
      suffix: ` / ${formatCompactNumber(totals.tokens_out)}`,
    },
    { label: "Subagent dispatches", value: formatCount(totals.agent_count) },
  ];

  return (
    <section className="ccfg-stats-card">
      <header className="ccfg-stats-card__header">
        <b>Claude stats</b>
        <span className="ccfg-stats-card__hint">all recorded sessions</span>
      </header>
      <div className="ccfg-stats-grid">
        {tiles.map((tile) => (
          <div key={tile.label} className="ccfg-stat-tile">
            <div className="ccfg-stat-tile__label">{tile.label}</div>
            <div className="ccfg-stat-tile__value">
              {tile.value}
              {tile.suffix !== undefined ? (
                <span className="ccfg-stat-tile__suffix">{tile.suffix}</span>
              ) : null}
            </div>
          </div>
        ))}
      </div>
      <button type="button" className="ccfg-link-btn select-none" onClick={onOpenSessions}>
        Sessions →
      </button>
      <CardRefreshFooter>
        <RefreshButton label="session stats" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </section>
  );
}
