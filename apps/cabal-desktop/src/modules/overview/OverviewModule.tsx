// Home Overview console: KPI row, grouped per-section status cards, and a readiness / alignment /
// activity band — all bound to /api/overview, deep-linking into the owning modules (T033).
import { useOverview } from "@/api/overview";
import { EmptyState } from "@/components/EmptyState";
import { KpiCard } from "@/components/KpiCard";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import { ActivityCard } from "./components/ActivityCard";
import { AlignmentCard } from "./components/AlignmentCard";
import { ReadinessGaugeCard } from "./components/ReadinessGaugeCard";
import { SectionStatusCard } from "./components/SectionStatusCard";
import { deriveActivityItems, deriveOverviewKpis, SIGNAL_LANES } from "./overviewConsole";
import {
  deriveOverviewActions,
  deriveOverviewCards,
  type OverviewCardSummary,
} from "./overviewSummary";
import "./OverviewModule.css";

export function OverviewModule() {
  const overviewQuery = useOverview();
  const { navigateToModule } = useModuleNavigation();

  if (overviewQuery.isPending) {
    return <EmptyState title="Loading overview…" />;
  }
  if (overviewQuery.isError) {
    return <EmptyState title="Could not load overview" body={overviewQuery.error.message} />;
  }

  const payload = overviewQuery.data;
  const cards = deriveOverviewCards(payload);
  const actions = deriveOverviewActions(payload, cards);
  const kpis = deriveOverviewKpis(payload, cards, actions);
  const activityItems = deriveActivityItems(actions);

  return (
    <div className="overview-console">
      <div className="overview-console__kpis">
        {kpis.map((kpi) => (
          <KpiCard
            key={kpi.key}
            label={kpi.label}
            value={kpi.value}
            unit={kpi.unit}
            delta={kpi.delta}
            deltaTone={kpi.deltaTone}
            hint={kpi.hint}
          />
        ))}
      </div>

      {SIGNAL_LANES.map((lane) => {
        const laneCards = lane.cardKeys
          .map((key) => cards.find((card) => card.key === key))
          .filter((card): card is OverviewCardSummary => card !== undefined);
        return (
          <section key={lane.key} className="overview-console__lane" aria-label={lane.title}>
            <h2 className="overview-console__lane-title select-none">
              {lane.title}
              <small>{lane.description}</small>
            </h2>
            <div className="overview-console__lane-grid">
              {laneCards.map((card) => (
                <SectionStatusCard
                  key={card.key}
                  card={card}
                  onOpen={() => navigateToModule(card.deepLinkModule)}
                />
              ))}
            </div>
          </section>
        );
      })}

      <div className="overview-console__band">
        <ReadinessGaugeCard cards={cards} />
        <AlignmentCard driftFlags={payload.drift_flags} onOpen={navigateToModule} />
        <ActivityCard
          items={activityItems}
          onOpen={navigateToModule}
          onOpenDiagnostics={() => navigateToModule("diagnostics")}
        />
      </div>
    </div>
  );
}
