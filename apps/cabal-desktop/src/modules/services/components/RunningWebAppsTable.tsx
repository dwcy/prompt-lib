import type { RunningWebApp } from "@/api/operations";

export interface RunningWebAppsTableProps {
  apps: RunningWebApp[];
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  isActionPending: boolean;
  onRefresh: () => void;
  onShutdown: (app: RunningWebApp) => void;
}

export function RunningWebAppsTable({
  apps,
  isLoading,
  isRefreshing,
  error,
  isActionPending,
  onRefresh,
  onShutdown,
}: RunningWebAppsTableProps) {
  return (
    <section className="svc-web-apps" aria-label="Running web apps">
      <header className="svc-web-apps__header">
        <div>
          <b>Running web apps</b>
          <span>Local processes with active TCP listening ports</span>
        </div>
        <button type="button" onClick={onRefresh} disabled={isRefreshing}>
          {isRefreshing ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error !== null ? (
        <p className="svc-web-apps__message svc-web-apps__message--error" role="alert">
          {error}
        </p>
      ) : isLoading ? (
        <p className="svc-web-apps__message">Scanning listening ports…</p>
      ) : apps.length === 0 ? (
        <p className="svc-web-apps__message">No running web apps found.</p>
      ) : (
        <div className="svc-web-apps__scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Port</th>
                <th scope="col">PID</th>
                <th scope="col">App name</th>
                <th scope="col">Location</th>
                <th scope="col">
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {apps.map((app) => (
                <tr key={`${app.pid}:${app.port}`}>
                  <td>
                    <code>{app.port}</code>
                  </td>
                  <td>
                    <code>{app.pid}</code>
                  </td>
                  <td className="svc-web-apps__name">{app.app_name}</td>
                  <td className="svc-web-apps__location" title={app.location ?? undefined}>
                    {app.location ?? "Unavailable"}
                  </td>
                  <td className="svc-web-apps__action">
                    <button
                      type="button"
                      disabled={isActionPending}
                      aria-label={`Shut down ${app.app_name} on port ${app.port}`}
                      onClick={() => onShutdown(app)}
                    >
                      Shut down
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
