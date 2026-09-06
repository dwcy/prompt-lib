// Console table card: uppercase column header row (name/scope/status/env/actions) matching the
// real /api/mcp fields, plus one row per connector — status dot, mono name (click to inspect),
// scope chips, StatePill status, env-readiness count, and right-aligned action buttons gated by
// the server's own `actions_available` (activate_global/activate_local/approve/disable) with a
// per-row Recheck affordance that selects the connector and forces a fresh status fetch.
import type { McpServer } from "@/api/operations";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { availableActions, envReadiness, mcpDotVariant, mcpVariant } from "@/modules/mcp/mcpStatus";

export interface McpConnectorsTableProps {
  servers: McpServer[];
  selectedName: string | null;
  onSelect: (name: string) => void;
  onRecheck: (server: McpServer) => void;
  onActivateGlobal: (server: McpServer) => void;
  onActivateLocal: (server: McpServer) => void;
  onApprove: (server: McpServer) => void;
  onDisable: (server: McpServer) => void;
}

export function McpConnectorsTable({
  servers,
  selectedName,
  onSelect,
  onRecheck,
  onActivateGlobal,
  onActivateLocal,
  onApprove,
  onDisable,
}: McpConnectorsTableProps) {
  return (
    <section className="mcp-table" aria-label="MCP connectors">
      <div className="mcp-table__columns" aria-hidden="true">
        <span />
        <span>Name</span>
        <span>Scope</span>
        <span>Status</span>
        <span>Env</span>
        <span>Actions</span>
      </div>
      <div className="mcp-rows">
        {servers.length === 0 ? (
          <EmptyState title="No connectors match these filters" />
        ) : (
          servers.map((server) => (
            <McpConnectorRow
              key={server.name}
              server={server}
              isSelected={server.name === selectedName}
              onSelect={onSelect}
              onRecheck={onRecheck}
              onActivateGlobal={onActivateGlobal}
              onActivateLocal={onActivateLocal}
              onApprove={onApprove}
              onDisable={onDisable}
            />
          ))
        )}
      </div>
    </section>
  );
}

interface McpConnectorRowProps {
  server: McpServer;
  isSelected: boolean;
  onSelect: (name: string) => void;
  onRecheck: (server: McpServer) => void;
  onActivateGlobal: (server: McpServer) => void;
  onActivateLocal: (server: McpServer) => void;
  onApprove: (server: McpServer) => void;
  onDisable: (server: McpServer) => void;
}

function McpConnectorRow({
  server,
  isSelected,
  onSelect,
  onRecheck,
  onActivateGlobal,
  onActivateLocal,
  onApprove,
  onDisable,
}: McpConnectorRowProps) {
  const actions = availableActions(server);
  const handlers: Record<string, (server: McpServer) => void> = {
    activate_global: onActivateGlobal,
    activate_local: onActivateLocal,
    approve: onApprove,
    disable: onDisable,
  };

  return (
    <div className={`mcp-row${isSelected ? " is-selected" : ""}`}>
      <span className={`mcp-dot mcp-dot--${mcpDotVariant(server.status)}`} aria-hidden="true" />
      <button
        type="button"
        className="mcp-row__name"
        aria-pressed={isSelected}
        onClick={() => onSelect(server.name)}
      >
        {server.name}
      </button>
      <span className="mcp-row__scopes">
        {server.scopes.map((item) => (
          <span key={item} className="mcp-scope-chip">
            {item}
          </span>
        ))}
      </span>
      <StatePill variant={mcpVariant(server.status)} label={server.status} />
      <span className="mcp-row__env">{envReadiness(server)}</span>
      <span className="mcp-row__actions">
        <button
          type="button"
          className="mcp-row__action--recheck"
          onClick={() => onRecheck(server)}
        >
          Recheck
        </button>
        {actions.map((action) => (
          <button
            key={action.kind}
            type="button"
            className={action.kind === "disable" ? "mcp-row__action--danger" : undefined}
            onClick={() => handlers[action.kind](server)}
          >
            {action.label}
          </button>
        ))}
      </span>
    </div>
  );
}
