// Service-style status card for one overview section: status dot, title, mono state label, and
// headline/measure fact lines — the whole card deep-links into its owning module.
import { isAttentionVariant, variantTone } from "../overviewConsole";
import type { OverviewCardSummary } from "../overviewSummary";

export interface SectionStatusCardProps {
  card: OverviewCardSummary;
  onOpen: () => void;
}

export function SectionStatusCard({ card, onOpen }: SectionStatusCardProps) {
  return (
    <button
      type="button"
      className="overview-service-card select-none"
      data-attention={isAttentionVariant(card.stateVariant)}
      onClick={onOpen}
      aria-label={`View ${card.title}`}
    >
      <span className="overview-service-card__head">
        <span className="overview-dot" data-tone={variantTone(card.stateVariant)} aria-hidden="true" />
        <b>{card.title}</b>
        <span className="overview-service-card__state">{card.stateVariant ?? "live"}</span>
      </span>
      <span className="overview-service-card__facts">
        {card.headline ?? "No summary reported"}
        <span className="overview-service-card__meta">measure {card.count ?? "live"} · open →</span>
      </span>
    </button>
  );
}
