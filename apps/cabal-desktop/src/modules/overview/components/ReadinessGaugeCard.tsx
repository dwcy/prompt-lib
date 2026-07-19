// Workspace-readiness card: donut gauge of steady overview sections plus a per-section legend of
// state-toned dots, computed from the same derived cards the status row renders.
import { Gauge } from "@/components/Gauge";
import { isAttentionVariant, variantTone } from "../overviewConsole";
import type { OverviewCardSummary } from "../overviewSummary";

export interface ReadinessGaugeCardProps {
  cards: OverviewCardSummary[];
}

export function ReadinessGaugeCard({ cards }: ReadinessGaugeCardProps) {
  const steadyCount = cards.filter((card) => !isAttentionVariant(card.stateVariant)).length;
  const fraction = cards.length > 0 ? steadyCount / cards.length : 0;
  const allSteady = steadyCount === cards.length;
  return (
    <section className="overview-card overview-readiness" aria-label="Workspace readiness">
      <header className="overview-card__header">
        <b>Workspace readiness</b>
        <span>{cards.length} signals</span>
      </header>
      <div className="overview-readiness__gauge">
        <Gauge
          fraction={fraction}
          value={`${steadyCount}/${cards.length}`}
          caption="signals steady"
          tone={allSteady ? "ok" : "warning"}
        />
      </div>
      <ul className="overview-readiness__legend">
        {cards.map((card) => (
          <li key={card.key}>
            <span className="overview-dot" data-tone={variantTone(card.stateVariant)} aria-hidden="true" />
            {card.title}
          </li>
        ))}
      </ul>
    </section>
  );
}
