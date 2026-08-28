// Services console screen: readiness gauge + per-service health grid, the "Local agent services"
// table with setup/start/stop actions, and a selected-service detail panel (prereqs, dashboard
// handoff, log stream) — per the cabal-console mock's isInfrastructure "Services" section.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  useDockerApps,
  useRunningWebApps,
  useServiceDashboard,
  useServices,
} from "@/api/operations";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { type UseActionResult, useAction } from "@/hooks/useAction";
import { useEventStream } from "@/lib/sse";
import { DockerAppsTable } from "@/modules/services/components/DockerAppsTable";
import { LocalAgentServicesTable } from "@/modules/services/components/LocalAgentServicesTable";
import { RunningWebAppsTable } from "@/modules/services/components/RunningWebAppsTable";
import { ServiceDetailPanel } from "@/modules/services/components/ServiceDetailPanel";
import { ServiceHealthGrid } from "@/modules/services/components/ServiceHealthGrid";
import { ServicesReadinessCard } from "@/modules/services/components/ServicesReadinessCard";
import { isSystemProcessLocation } from "@/modules/services/isSystemProcessLocation";
import "./ServicesModule.css";

export function ServicesModule() {
  const query = useServices();
  const runningAppsQuery = useRunningWebApps();
  const dockerAppsQuery = useDockerApps();
  const queryClient = useQueryClient();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [setupJobId, setSetupJobId] = useState<string | null>(null);
  const [hideSystemProcesses, setHideSystemProcesses] = useState(true);
  const setup = useAction("services.setup");
  const start = useAction("services.start");
  const stop = useAction("services.stop");
  const stopRunningApp = useAction("services.running_app.stop");
  const startDockerApp = useAction("services.docker.start");
  const stopDockerApp = useAction("services.docker.stop");
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
    if (stopRunningApp.phase === "succeeded") {
      queryClient.invalidateQueries({ queryKey: ["cabal", "global", "runningWebApps"] });
      stopRunningApp.reset();
    }
    if ([startDockerApp, stopDockerApp].some((action) => action.phase === "succeeded")) {
      queryClient.invalidateQueries({ queryKey: ["cabal", "global", "dockerApps"] });
      startDockerApp.reset();
      stopDockerApp.reset();
    }
  }, [
    dashboardAction,
    queryClient,
    setup,
    start,
    startDockerApp,
    stop,
    stopDockerApp,
    stopRunningApp,
  ]);

  if (query.isPending) return <EmptyState title="Loading agent services…" />;
  if (query.isError)
    return <EmptyState title="Could not load services" body={query.error.message} />;

  const readyCount = query.data.counts.running + query.data.counts.stopped;
  const runningApps = runningAppsQuery.data?.apps ?? [];
  const systemProcessCount = runningApps.filter((app) =>
    isSystemProcessLocation(app.location),
  ).length;
  const visibleRunningApps = hideSystemProcesses
    ? runningApps.filter((app) => !isSystemProcessLocation(app.location))
    : runningApps;

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

      <RunningWebAppsTable
        apps={visibleRunningApps}
        hiddenSystemCount={hideSystemProcesses ? systemProcessCount : 0}
        hideSystemProcesses={hideSystemProcesses}
        onToggleHideSystemProcesses={() => setHideSystemProcesses((value) => !value)}
        isLoading={runningAppsQuery.isPending}
        isRefreshing={runningAppsQuery.isFetching}
        error={runningAppsQuery.isError ? runningAppsQuery.error.message : null}
        isActionPending={stopRunningApp.phase !== "idle"}
        onRefresh={() => void runningAppsQuery.refetch()}
        onShutdown={(app) =>
          stopRunningApp.prepare({
            pid: app.pid,
            port: app.port,
            started_at: app.started_at,
          })
        }
      />

      <DockerAppsTable
        payload={dockerAppsQuery.data ?? null}
        isLoading={dockerAppsQuery.isPending}
        isRefreshing={dockerAppsQuery.isFetching}
        error={dockerAppsQuery.isError ? dockerAppsQuery.error.message : null}
        isActionPending={startDockerApp.phase !== "idle" || stopDockerApp.phase !== "idle"}
        onRefresh={() => void dockerAppsQuery.refetch()}
        onStart={(container) =>
          startDockerApp.prepare({
            container_id: container.container_id,
            expected_state: container.state,
          })
        }
        onStop={(container) =>
          stopDockerApp.prepare({
            container_id: container.container_id,
            expected_state: container.state,
          })
        }
      />

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
      <ServiceDialog title="Shut Down Web App" action={stopRunningApp} />
      <ServiceDialog title="Start Docker App" action={startDockerApp} />
      <ServiceDialog title="Stop Docker App" action={stopDockerApp} />
    </div>
  );
}

function ServiceDialog({ title, action }: { title: string; action: UseActionResult }) {
  return <ConfirmDialog action={action} actionTitle={title} />;
}
