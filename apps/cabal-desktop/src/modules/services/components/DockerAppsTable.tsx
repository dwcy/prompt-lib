import type { DockerApp, DockerAppsPayload } from "@/api/operations";
import { StatePill, type StatePillVariant } from "@/components/StatePill";

export interface DockerAppsTableProps {
  payload: DockerAppsPayload | null;
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  isActionPending: boolean;
  onRefresh: () => void;
  onStart: (app: DockerApp) => void;
  onStop: (app: DockerApp) => void;
}

export function DockerAppsTable({
  payload,
  isLoading,
  isRefreshing,
  error,
  isActionPending,
  onRefresh,
  onStart,
  onStop,
}: DockerAppsTableProps) {
  const containers = payload?.containers ?? [];
  const message = error ?? payload?.message ?? null;

  return (
    <section className="svc-web-apps svc-docker-apps" aria-label="Docker apps">
      <header className="svc-web-apps__header">
        <div>
          <b>Docker apps</b>
          <span>{dockerSummary(payload)}</span>
        </div>
        <button type="button" onClick={onRefresh} disabled={isRefreshing}>
          {isRefreshing ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {message !== null ? (
        <p className="svc-web-apps__message svc-web-apps__message--error" role="alert">
          {message}
        </p>
      ) : isLoading ? (
        <p className="svc-web-apps__message">Loading Docker containers…</p>
      ) : containers.length === 0 ? (
        <p className="svc-web-apps__message">No Docker containers found.</p>
      ) : (
        <div className="svc-web-apps__scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Image</th>
                <th scope="col">Ports</th>
                <th scope="col">Status</th>
                <th scope="col">Project / location</th>
                <th scope="col">
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {containers.map((container) => (
                <DockerAppRow
                  key={container.container_id}
                  container={container}
                  isActionPending={isActionPending}
                  onStart={onStart}
                  onStop={onStop}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function DockerAppRow({
  container,
  isActionPending,
  onStart,
  onStop,
}: {
  container: DockerApp;
  isActionPending: boolean;
  onStart: (app: DockerApp) => void;
  onStop: (app: DockerApp) => void;
}) {
  return (
    <tr>
      <td className="svc-web-apps__name">{container.name}</td>
      <td className="svc-docker-apps__image" title={container.image}>
        {container.image}
      </td>
      <td className="svc-docker-apps__ports">{container.ports || "—"}</td>
      <td>
        <div className="svc-docker-apps__status">
          <StatePill variant={dockerStateVariant(container.state)} label={container.state} />
          <span>{container.health ?? container.status}</span>
        </div>
      </td>
      <td className="svc-docker-apps__project">
        <strong>{container.project ?? container.service ?? "Standalone"}</strong>
        <span title={container.location ?? undefined}>{container.location ?? "—"}</span>
      </td>
      <td className="svc-web-apps__action">
        {container.can_stop ? (
          <button
            type="button"
            disabled={isActionPending}
            aria-label={`Stop Docker container ${container.name}`}
            onClick={() => onStop(container)}
          >
            Stop
          </button>
        ) : container.can_start ? (
          <button
            type="button"
            className="svc-docker-apps__action--start"
            disabled={isActionPending}
            aria-label={`Start Docker container ${container.name}`}
            onClick={() => onStart(container)}
          >
            Start
          </button>
        ) : (
          <span className="svc-docker-apps__no-action">—</span>
        )}
      </td>
    </tr>
  );
}

function dockerSummary(payload: DockerAppsPayload | null): string {
  if (payload === null) return "All local containers across every state";
  if (!payload.available) return "Docker is not installed";
  if (!payload.daemon_running) return "Docker engine is not running";
  const { total, running, stopped, other } = payload.counts;
  const otherText = other > 0 ? ` · ${other} other` : "";
  return `${total} total · ${running} running · ${stopped} stopped${otherText}`;
}

function dockerStateVariant(state: string): StatePillVariant {
  if (state === "running") return "running";
  if (state === "paused" || state === "restarting") return "degraded";
  if (state === "dead" || state === "removing") return "failed";
  return "closed";
}
