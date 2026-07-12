// One Overview summary card: optional state pill, headline/count, and a deep-link button.
import { StatePill } from "@/components/StatePill";
import type { OverviewCardSummary } from "@/modules/overview/overviewSummary";

export interface OverviewCardProps {
  card: OverviewCardSummary;
  onView: (moduleKey: OverviewCardSummary["deepLinkModule"]) => void;
}

export function OverviewCard({ card, onView }: OverviewCardProps) {
  const hasCount = card.count !== null;

  return (
    <article className="overview-card">
      <header className="overview-card__header">
        <h3 className="overview-card__title">{card.title}</h3>
        {card.stateVariant !== null ? <StatePill variant={card.stateVariant} /> : null}
      </header>
      <p className="overview-card__body">
        {card.headline ?? (hasCount ? `${card.count} item(s)` : "No summary available")}
      </p>
      {card.headline !== null && hasCount ? (
        <p className="overview-card__count select-none">{card.count} item(s)</p>
      ) : null}
      <button
        type="button"
        className="overview-card__link select-none"
        onClick={() => onView(card.deepLinkModule)}
      >
        View {card.title}
      </button>
    </article>
  );
}
