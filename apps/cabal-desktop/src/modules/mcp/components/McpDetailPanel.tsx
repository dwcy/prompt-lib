// Selected-connector detail/expansion panel: connection state, scope chips, the recorded launch
// command, and the required-environment-variable list rendered as divider rows with mono values —
// restyled from the original inline inspector, same fields (server.env_status), same actions.
import type { McpServer } from "@/api/operations";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { availableActions, mcpVariant } from "@/modules/mcp/mcpStatus";

export interface McpDetailPanelProps {
  server: McpServer | null;
  refreshing: boolean;
  onRecheck: () => void;
  onActivateGlobal: (server: McpServer) => void;
  onActivateLocal: (server: McpServer) => void;
  onApprove: (server: McpServer) => void;
  onDisable: (server: McpServer) => void;
}

export function McpDetailPanel({
  server,
  refreshing,
  onRecheck,
  onActivateGlobal,
  onActivateLocal,
  onApprove,
  onDisable,
}: McpDetailPanelProps) {
  if (server === null)
    return (
      <aside className="mcp-detail">
        <EmptyState title="Select a connector" />
      </aside>
    );

  const actions = availableActions(server);
  const handlers: Record<string, (server: McpServer) => void> = {
    activate_global: onActivateGlobal,
    activate_local: onActivateLocal,
    approve: onApprove,
    disable: onDisable,
  };

  return (
    <aside className="mcp-detail">
      <header className="mcp-detail__header">
        <div>
          <span className="mcp-eyebrow">Scope inspector</span>
          <h2>{server.name}</h2>
        </div>
        <button type="button" onClick={onRecheck} disabled={refreshing}>
          {refreshing ? "Checking" : "Recheck"}
        </button>
      </header>

      <div className="mcp-detail__connection">
        <StatePill variant={mcpVariant(server.status)} label={server.status} />
        <span>{server.active ? "active configuration" : "available configuration"}</span>
      </div>

      <div className="mcp-detail__scopes">
        {server.scopes.map((item) => (
          <span key={item} className="mcp-scope-chip">
            {item}
          </span>
        ))}
      </div>

      <pre className="mcp-detail__command">{server.command || "No command recorded"}</pre>

      <dl className="mcp-detail__env">
        {server.env_status.length === 0 ? (
          <p className="mcp-detail__env-empty">No required environment variables</p>
        ) : (
          server.env_status.map((item) => (
            <div key={item.name} className={item.present ? "is-ready" : "is-missing"}>
              <dt>{item.name}</dt>
              <dd>{item.present ? "ready" : "missing"}</dd>
            </div>
          ))
        )}
      </dl>

      {actions.length > 0 ? (
        <div className="mcp-detail__actions">
          {actions.map((action) => (
            <button
              key={action.kind}
              type="button"
              className={action.kind === "disable" ? "mcp-detail__action--danger" : undefined}
              onClick={() => handlers[action.kind](server)}
            >
              {action.label}
            </button>
          ))}
        </div>
      ) : null}
    </aside>
  );
}
