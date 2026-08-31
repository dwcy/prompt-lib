// Selected-service detail panel: runtime command, prereq checklist, dashboard handoff, and the
// log stream pane. Not part of the compact mock cards/table above, but required to keep the prereq
// gating, dashboard handoff, and log-stream functionality the previous layout exposed.
import type { ServiceRow } from "@/api/operations";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { EmptyState } from "@/components/EmptyState";
import { LogStream } from "@/components/LogStream";
import { RefreshButton } from "@/components/RefreshButton";
import type { StreamConnectionState, StreamEvent } from "@/lib/sse";

export interface ServiceDetailPanelProps {
  service: ServiceRow | null;
  dashboardMessage?: string;
  dashboardCommand?: string;
  onDashboard: (service: ServiceRow) => void;
  logEvents: StreamEvent[];
  logConnectionState: StreamConnectionState;
  onRefresh: () => void;
  isFetching: boolean;
}

export function ServiceDetailPanel({
  service,
  dashboardMessage,
  dashboardCommand,
  onDashboard,
  logEvents,
  logConnectionState,
  onRefresh,
  isFetching,
}: ServiceDetailPanelProps) {
  if (service === null) {
    return (
      <section className="svc-detail">
        <EmptyState title="Select a service" />
      </section>
    );
  }

  return (
    <section className="svc-detail" aria-label={`${service.label} detail`}>
      <header className="svc-detail__header">
        <span className="svc-detail__eyebrow select-none">{service.console_name}</span>
        <h2>{service.label}</h2>
      </header>
      <pre className="svc-detail__command">{service.run_command}</pre>

      <dl className="svc-prereqs">
        {service.prereqs.length === 0 ? (
          <p className="svc-prereqs__empty">No prerequisites.</p>
        ) : (
          service.prereqs.map((item) => (
            <div key={item.key} className={item.ok ? "is-ok" : "is-blocked"}>
              <dt>{item.key}</dt>
              <dd>{item.message || "Ready"}</dd>
            </div>
          ))
        )}
      </dl>

      {service.dashboard_handoff ? (
        <div className="svc-dashboard">
          <strong>Dashboard handoff</strong>
          <p>{dashboardMessage ?? "Checking dashboard command…"}</p>
          {dashboardCommand !== undefined ? <code>{dashboardCommand}</code> : null}
          <button type="button" onClick={() => onDashboard(service)}>
            Open dashboard
          </button>
        </div>
      ) : null}

      <div className="svc-log">
        <header className="svc-log__header select-none">
          <span>Captured output</span>
          <strong>{service.log_path || "No log path"}</strong>
        </header>
        {!service.log_stream_available ? (
          <EmptyState title="No log stream available" />
        ) : (
          <LogStream events={logEvents} connectionState={logConnectionState} />
        )}
      </div>
      <CardRefreshFooter>
        <RefreshButton label="service detail" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </section>
  );
}
