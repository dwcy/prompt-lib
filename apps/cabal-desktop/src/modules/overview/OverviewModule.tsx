// Home Overview console: KPI row, grouped per-section status cards, and a readiness / alignment /
// activity band — all bound to /api/overview, deep-linking into the owning modules (T033).
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useJob } from "@/api/jobs";
import { useOverview } from "@/api/overview";
import { useProviderState } from "@/api/projectLifecycle";
import { queryKeys } from "@/api/queryKeys";
import { useSystemOverview } from "@/api/systemOverview";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { KpiCard } from "@/components/KpiCard";
import { useAction } from "@/hooks/useAction";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import { ActivityCard } from "./components/ActivityCard";
import { AlignmentCard } from "./components/AlignmentCard";
import { GitHubAccountPanel } from "./components/GitHubAccountPanel";
import { ReadinessGaugeCard } from "./components/ReadinessGaugeCard";
import { SectionStatusCard } from "./components/SectionStatusCard";
import { ServiceStatusRow } from "./components/ServiceStatusRow";
import { SystemOverviewPanel } from "./components/SystemOverviewPanel";
import { TerminalPanel } from "./components/TerminalPanel";
import { useOverviewKpis } from "./hooks/useOverviewKpis";
import { deriveActivityItems, SIGNAL_LANES } from "./overviewConsole";
import {
  deriveOverviewActions,
  deriveOverviewCards,
  type OverviewCardSummary,
} from "./overviewSummary";
import "./OverviewModule.css";

export function OverviewModule() {
  const queryClient = useQueryClient();
  const overviewQuery = useOverview();
  const providerQuery = useProviderState();
  const systemQuery = useSystemOverview();
  const kpis = useOverviewKpis();
  const switchAction = useAction("provider.switch_account");
  const updateAction = useAction("system.update");
  const updateJob = useJob(updateAction.jobId ?? "", {
    enabled: updateAction.jobId !== null,
    refetchInterval: 1_000,
  });
  const { navigateToModule } = useModuleNavigation();

  useEffect(() => {
    if (switchAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("provider", "state") });
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("provider", "repos") });
    void queryClient.invalidateQueries({
      predicate: (query) => query.queryKey[2] === "homeOverview",
    });
  }, [queryClient, switchAction.phase]);

  useEffect(() => {
    if (
      updateJob.data === undefined ||
      !["succeeded", "failed", "cancelled"].includes(updateJob.data.state)
    ) {
      return;
    }
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("system", "overview") });
  }, [queryClient, updateJob.data]);

  if (overviewQuery.isPending) {
    return <EmptyState title="Loading overview…" />;
  }
  if (overviewQuery.isError) {
    return <EmptyState title="Could not load overview" body={overviewQuery.error.message} />;
  }

  const payload = overviewQuery.data;
  const cards = deriveOverviewCards(payload);
  const actions = deriveOverviewActions(payload, cards);
  const activityItems = deriveActivityItems(actions);

  return (
    <div className="overview-console">
      <div className="overview-console__identity-row">
        <SystemOverviewPanel
          state={systemQuery.data}
          isPending={systemQuery.isPending}
          error={systemQuery.isError ? systemQuery.error.message : null}
          updateBusy={
            updateAction.phase === "preparing" ||
            updateAction.phase === "executing" ||
            updateJob.data?.state === "queued" ||
            updateJob.data?.state === "running"
          }
          onUpdate={() => updateAction.prepare({})}
        />

        <GitHubAccountPanel
          state={providerQuery.data}
          isPending={providerQuery.isPending}
          error={providerQuery.isError ? providerQuery.error.message : null}
          switchBusy={switchAction.phase === "preparing" || switchAction.phase === "executing"}
          onSwitch={(user, host) => switchAction.prepare({ user, host })}
        />
      </div>

      <TerminalPanel
        state={systemQuery.data}
        isPending={systemQuery.isPending}
        error={systemQuery.isError ? systemQuery.error.message : null}
      />

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

      <ServiceStatusRow />

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

      <ConfirmDialog action={switchAction} actionTitle="Switch GitHub account" />
      <ConfirmDialog action={updateAction} actionTitle="Update Cabal" />
    </div>
  );
}
