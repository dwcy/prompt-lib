// Home Overview: six summary cards (dashboard/sessions/account/doctor/knowledge/security), drift
// badges, and deep links into the corresponding module (T033).
import { useOverview } from "@/api/overview";
import { EmptyState } from "@/components/EmptyState";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import { DriftBadges } from "@/modules/overview/components/DriftBadges";
import { OverviewCard } from "@/modules/overview/components/OverviewCard";
import { deriveOverviewCards } from "@/modules/overview/overviewSummary";

export function OverviewModule() {
  const overviewQuery = useOverview();
  const { navigateToModule } = useModuleNavigation();

  if (overviewQuery.isPending) {
    return <EmptyState title="Loading overview…" />;
  }
  if (overviewQuery.isError) {
    return <EmptyState title="Could not load overview" body={overviewQuery.error.message} />;
  }

  const cards = deriveOverviewCards(overviewQuery.data);

  return (
    <div className="overview-module">
      <DriftBadges driftFlags={overviewQuery.data.drift_flags} />
      <div className="overview-grid">
        {cards.map((card) => (
          <OverviewCard key={card.key} card={card} onView={navigateToModule} />
        ))}
      </div>
    </div>
  );
}
