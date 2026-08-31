import type { MachineTool, SystemOverview } from "@/api/systemOverview";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { RefreshButton } from "@/components/RefreshButton";

const CORE_TOOL_KEYS = new Set(["git", "python", "node", "npm", "pnpm", "dotnet"]);

export interface SystemOverviewPanelProps {
  state: SystemOverview | undefined;
  isPending: boolean;
  error: string | null;
  updateBusy: boolean;
  onUpdate: () => void;
  onRefresh: () => void;
  isFetching: boolean;
}

export function SystemOverviewPanel({
  state,
  isPending,
  error,
  updateBusy,
  onUpdate,
  onRefresh,
  isFetching,
}: SystemOverviewPanelProps) {
  if (isPending) {
    return (
      <section className="overview-system-panel" aria-label="Machine snapshot">
        <p className="overview-system-panel__message">Reading this computer…</p>
      </section>
    );
  }
  if (error !== null || state === undefined) {
    return (
      <section className="overview-system-panel" aria-label="Machine snapshot">
        <p className="overview-system-panel__message overview-system-panel__message--error">
          Computer information is unavailable{error ? `: ${error}` : "."}
        </p>
      </section>
    );
  }

  const coreTools = state.machine.tools.filter((tool) => CORE_TOOL_KEYS.has(tool.key));
  const additionalTools = state.machine.tools.filter(
    (tool) => !CORE_TOOL_KEYS.has(tool.key) && tool.installed,
  );
  const updateAvailable = state.cabal.status === "behind";
  const revisionUnavailable = state.cabal.latest_hash === null;

  return (
    <section className="overview-system-panel" aria-label="Machine snapshot">
      <div className="overview-system-panel__title">
        <b>Machine snapshot</b>
        <span>host probes, live versions</span>
      </div>
      <header className="overview-system-panel__header">
        <div className="overview-system-panel__machine">
          <span className="overview-system-panel__machine-icon" aria-hidden="true">
            <ComputerIcon />
          </span>
          <span>
            <strong>
              {state.machine.os} {state.machine.release}
            </strong>
            <small>Package manager: {state.machine.package_manager ?? "not detected"}</small>
          </span>
        </div>

        <section className="overview-system-panel__cabal" aria-label="Cabal version">
          <strong className="overview-system-panel__cabal-name">
            Cabal <small>{state.cabal.version}</small>
          </strong>
          <code>{state.cabal.latest_hash ?? "unknown"}</code>
          <time>{state.cabal.latest_date || "date unavailable"}</time>
          {updateAvailable ? (
            <button
              className="overview-system-panel__update-link"
              type="button"
              onClick={onUpdate}
              disabled={updateBusy}
            >
              {updateBusy
                ? "Updating…"
                : `Update${state.cabal.behind_count ? ` (${state.cabal.behind_count})` : ""}`}
            </button>
          ) : (
            <strong className="overview-system-panel__version-state">
              {revisionUnavailable ? "Restart to refresh" : "Latest version"}
            </strong>
          )}
        </section>
      </header>

      <ul className="overview-system-panel__toolchain" aria-label="Core toolchain">
        {coreTools.map((tool) => (
          <ToolVersion key={tool.key} tool={tool} />
        ))}
      </ul>

      {additionalTools.length > 0 ? (
        <div className="overview-system-panel__detected">
          <small>{additionalTools.length} more detected</small>
          <div>
            {additionalTools.map((tool) => (
              <span key={tool.key} title={tool.version ?? tool.label}>
                <i aria-hidden="true" />
                <b>{tool.label}</b>
                {tool.version !== null ? <code>{shortVersion(tool.version)}</code> : null}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      <CardRefreshFooter>
        <RefreshButton label="machine snapshot" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </section>
  );
}

function ToolVersion({ tool }: { tool: MachineTool }) {
  return (
    <li className="overview-system-tool" data-installed={tool.installed}>
      <span>
        <i aria-hidden="true" />
        {tool.label}
      </span>
      <strong>{tool.installed ? shortVersion(tool.version) : "Not found"}</strong>
    </li>
  );
}

function shortVersion(value: string | null): string {
  if (value === null || value.length === 0) return "Installed";
  const match = value.match(/v?\d+\.\d+(?:\.\d+)?(?:[-+.][\w.-]+)?/);
  return match?.[0] ?? value;
}

function ComputerIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="4" width="18" height="13" rx="2" />
      <path d="M8 21h8m-4-4v4" />
    </svg>
  );
}
