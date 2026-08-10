// Services console screen: readiness gauge + per-service health grid, the "Local agent services"
// table with setup/start/stop actions, and a selected-service detail panel (prereqs, dashboard
// handoff, log stream) — per the cabal-console mock's isInfrastructure "Services" section.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useServiceDashboard, useServices } from "@/api/operations";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { type UseActionResult, useAction } from "@/hooks/useAction";
import { useEventStream } from "@/lib/sse";
import { LocalAgentServicesTable } from "@/modules/services/components/LocalAgentServicesTable";
import { ServiceDetailPanel } from "@/modules/services/components/ServiceDetailPanel";
import { ServiceHealthGrid } from "@/modules/services/components/ServiceHealthGrid";
import { ServicesReadinessCard } from "@/modules/services/components/ServicesReadinessCard";
import "./ServicesModule.css";

export function ServicesModule() {
  const query = useServices();
  const queryClient = useQueryClient();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [setupJobId, setSetupJobId] = useState<string | null>(null);
  const setup = useAction("services.setup");
  const start = useAction("services.start");
  const stop = useAction("services.stop");
  const dashboardAction = useAction("services.dashboard");

  const services = query.data?.services ?? [];
  const selected = services.find((service) => service.key === selectedKey) ?? services[0] ?? null;
  const dashboard = useServiceDashboard(
    selected?.key ?? null,
    Boolean(selected?.dashboard_handoff),
  );
  const logStream = useEventStream(
    selected === null
      ? "/api/services/none/logs/stream"
      : `/api/services/${selected.key}/logs/stream`,
    { enabled: selected?.log_stream_available ?? false },
  );

  useEffect(() => {
    if (selectedKey !== null && services.some((service) => service.key === selectedKey)) return;
    setSelectedKey(services[0]?.key ?? null);
  }, [selectedKey, services]);

  useEffect(() => {
    if (setup.phase === "succeeded" && setup.jobId !== null) setSetupJobId(setup.jobId);
    if ([setup, start, stop, dashboardAction].some((action) => action.phase === "succeeded")) {
      queryClient.invalidateQueries({ queryKey: ["cabal", "global", "services"] });
      setup.reset();
      start.reset();
      stop.reset();
      dashboardAction.reset();
    }
  }, [dashboardAction, queryClient, setup, start, stop]);

  if (query.isPending) return <EmptyState title="Loading agent services…" />;
  if (query.isError)
    return <EmptyState title="Could not load services" body={query.error.message} />;

  const readyCount = query.data.counts.running + query.data.counts.stopped;

  return (
    <div className="svc-console">
      <section className="svc-top">
        <ServicesReadinessCard
          services={services}
          readyCount={readyCount}
          totalCount={query.data.counts.total}
        />
        <ServiceHealthGrid services={services} />
      </section>

      {setupJobId !== null ? <JobPane jobId={setupJobId} /> : null}

      <LocalAgentServicesTable
        services={services}
        selectedKey={selected?.key ?? null}
        onSelect={setSelectedKey}
        onSetup={(service) => setup.prepare({ key: service.key })}
        onStart={(service) => start.prepare({ key: service.key })}
        onStop={(service) => stop.prepare({ key: service.key })}
      />

      <ServiceDetailPanel
        service={selected}
        dashboardMessage={dashboard.data?.message}
        dashboardCommand={dashboard.data?.argv?.join(" ")}
        onDashboard={(service) => dashboardAction.prepare({ key: service.key })}
        logEvents={logStream.events}
        logConnectionState={logStream.state}
      />

      <ServiceDialog title="Set Up Service" action={setup} />
      <ServiceDialog title="Start Service" action={start} />
      <ServiceDialog title="Stop Service" action={stop} />
      <ServiceDialog title="Open Service Dashboard" action={dashboardAction} />
    </div>
  );
}

function ServiceDialog({ title, action }: { title: string; action: UseActionResult }) {
  return (
    <ConfirmDialog
      isOpen={action.phase !== "idle" && action.phase !== "succeeded"}
      actionTitle={title}
      ticket={action.ticket}
      phase={action.phase}
      reviewNotice={action.reviewNotice}
      error={action.error}
      onConfirm={action.confirm}
      onCancel={action.reset}
    />
  );
}
