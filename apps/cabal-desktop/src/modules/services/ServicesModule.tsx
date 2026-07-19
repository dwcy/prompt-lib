import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  type ServiceRow,
  type ServiceState,
  useServiceDashboard,
  useServices,
} from "@/api/operations";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { LogStream } from "@/components/LogStream";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import { useEventStream } from "@/lib/sse";

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

  const dependencyLines = useMemo(() => serviceDependencyLines(services), [services]);

  if (query.isPending) return <EmptyState title="Loading agent services..." />;
  if (query.isError)
    return <EmptyState title="Could not load services" body={query.error.message} />;

  return (
    <div className="services-workspace">
      <section className="services-command-center">
        <div>
          <span className="us3-eyebrow">Runtime runway</span>
          <h1>Agent services</h1>
          <p>
            Setup, start, stop, and tail local agent infrastructure without losing dependency
            context.
          </p>
        </div>
        <div className="services-command-center__metrics">
          <Metric label="running" value={String(query.data.counts.running)} />
          <Metric label="stopped" value={String(query.data.counts.stopped)} />
          <Metric label="blocked" value={String(query.data.counts.blocked)} />
          <Metric label="not set up" value={String(query.data.counts.not_set_up)} />
        </div>
      </section>

      {setupJobId !== null ? <JobPane jobId={setupJobId} /> : null}

      <section className="services-runway">
        <div className="service-map">
          {services.map((service) => (
            <button
              key={service.key}
              type="button"
              className={`service-node-card${selected?.key === service.key ? " is-active" : ""}`}
              aria-pressed={selected?.key === service.key}
              onClick={() => setSelectedKey(service.key)}
            >
              <span className="service-node-card__identity">
                <strong>{service.label}</strong>
                <small>{service.console_name}</small>
              </span>
              <StatePill variant={serviceVariant(service.state)} label={service.state} />
              <ServiceLifecycle state={service.state} />
              <span className="service-node-card__dependency">
                {service.depends_on.length === 0
                  ? "standalone"
                  : `after ${service.depends_on.join(", ")}`}
              </span>
            </button>
          ))}
          <div className="service-dependency-lines">
            {dependencyLines.length === 0 ? (
              <span>No service dependencies</span>
            ) : (
              dependencyLines.map((line) => <span key={line}>{line}</span>)
            )}
          </div>
        </div>

        <ServiceInspector
          service={selected}
          dashboardMessage={dashboard.data?.message}
          dashboardCommand={dashboard.data?.argv?.join(" ")}
          onSetup={(service) => setup.prepare({ key: service.key })}
          onStart={(service) => start.prepare({ key: service.key })}
          onStop={(service) => stop.prepare({ key: service.key })}
          onDashboard={(service) => dashboardAction.prepare({ key: service.key })}
        />

        <div className="service-log-panel">
          <header>
            <span className="us3-eyebrow">Captured output</span>
            <strong>{selected?.log_path ?? "No service selected"}</strong>
          </header>
          {selected === null || !selected.log_stream_available ? (
            <EmptyState title="No log stream available" />
          ) : (
            <LogStream events={logStream.events} connectionState={logStream.state} />
          )}
        </div>
      </section>

      <ServiceDialog title="Set Up Service" action={setup} />
      <ServiceDialog title="Start Service" action={start} />
      <ServiceDialog title="Stop Service" action={stop} />
      <ServiceDialog title="Open Service Dashboard" action={dashboardAction} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <span>
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

interface ServiceInspectorProps {
  service: ServiceRow | null;
  dashboardMessage?: string;
  dashboardCommand?: string;
  onSetup: (service: ServiceRow) => void;
  onStart: (service: ServiceRow) => void;
  onStop: (service: ServiceRow) => void;
  onDashboard: (service: ServiceRow) => void;
}

function ServiceInspector({
  service,
  dashboardMessage,
  dashboardCommand,
  onSetup,
  onStart,
  onStop,
  onDashboard,
}: ServiceInspectorProps) {
  if (service === null)
    return (
      <aside className="service-inspector">
        <EmptyState title="Select a service" />
      </aside>
    );
  const prereqsReady = service.prereqs.every((item) => item.ok);
  const canSetup = service.runnable && service.state === "not_set_up";
  const canStart = service.runnable && service.state === "stopped" && prereqsReady;
  const canStop = service.runnable && service.state === "running";
  return (
    <aside className="service-inspector">
      <header className="service-inspector__header">
        <div>
          <span className="us3-eyebrow">{service.console_name}</span>
          <h2>{service.label}</h2>
        </div>
        <StatePill variant={serviceVariant(service.state)} label={service.state} />
      </header>
      <p className="service-inspector__description">{service.description}</p>
      <ServiceLifecycle state={service.state} detailed />
      <pre>{service.run_command}</pre>
      <div className="service-runtime-meta">
        <span>
          <small>Process</small>
          <strong>{service.pid === null ? "none" : service.pid}</strong>
        </span>
        <span>
          <small>Port</small>
          <strong>{service.default_port ?? "dynamic"}</strong>
        </span>
        <span>
          <small>Owner</small>
          <strong>{service.started_by_app ? "Cabal" : "external"}</strong>
        </span>
      </div>
      <div className={`service-next-action service-next-action--${service.state}`}>
        <div>
          <span className="us3-eyebrow">Next control</span>
          <strong>{serviceNextLabel(service, prereqsReady)}</strong>
        </div>
        {canSetup ? (
          <button type="button" onClick={() => onSetup(service)}>
            Set up
          </button>
        ) : canStart ? (
          <button type="button" onClick={() => onStart(service)}>
            Start service
          </button>
        ) : canStop ? (
          <button type="button" className="danger-button" onClick={() => onStop(service)}>
            Stop service
          </button>
        ) : null}
      </div>
      <div className="service-prereq-stack">
        {service.prereqs.length === 0 ? (
          <span>No prerequisites</span>
        ) : (
          service.prereqs.map((item) => (
            <article key={item.key} className={item.ok ? "is-ok" : "is-blocked"}>
              <strong>{item.key}</strong>
              <p>{item.message || "Ready"}</p>
            </article>
          ))
        )}
      </div>
      {service.dashboard_handoff ? (
        <div className="service-dashboard-handoff">
          <strong>Dashboard handoff</strong>
          <p>{dashboardMessage ?? "Checking dashboard command..."}</p>
          {dashboardCommand ? <code>{dashboardCommand}</code> : null}
          <button type="button" onClick={() => onDashboard(service)}>
            Open dashboard
          </button>
        </div>
      ) : null}
    </aside>
  );
}

function ServiceLifecycle({
  state,
  detailed = false,
}: {
  state: ServiceState;
  detailed?: boolean;
}) {
  const reachedSetup = state !== "not_set_up";
  const reachedReady = state === "stopped" || state === "running";
  const reachedRunning = state === "running";
  return (
    <ol className={`service-lifecycle${detailed ? " service-lifecycle--detailed" : ""}`}>
      <li
        className={reachedSetup ? "is-complete" : "is-current"}
        aria-current={reachedSetup ? undefined : "step"}
      >
        Setup
      </li>
      <li
        className={reachedReady ? "is-complete" : reachedSetup ? "is-current" : ""}
        aria-current={!reachedReady && reachedSetup ? "step" : undefined}
      >
        Ready
      </li>
      <li
        className={reachedRunning ? "is-complete is-current" : ""}
        aria-current={reachedRunning ? "step" : undefined}
      >
        Running
      </li>
    </ol>
  );
}

function serviceNextLabel(service: ServiceRow, prereqsReady: boolean) {
  if (!service.runnable || service.state === "info_only") return "Status is informational";
  if (service.state === "not_set_up") return "Install service assets";
  if (!prereqsReady || service.state === "blocked") return "Resolve prerequisite blockers";
  if (service.state === "stopped") return "Ready to launch";
  return "Service is live";
}

function ServiceDialog({ title, action }: { title: string; action: ReturnType<typeof useAction> }) {
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

function serviceVariant(state: ServiceState): StatePillVariant {
  switch (state) {
    case "running":
      return "ok";
    case "stopped":
      return "unavailable";
    case "not_set_up":
      return "missing";
    case "blocked":
      return "error";
    case "info_only":
      return "degraded";
  }
}

function serviceDependencyLines(services: ServiceRow[]) {
  return services.flatMap((service) =>
    service.depends_on.map((dependency) => `${dependency} -> ${service.key}`),
  );
}
