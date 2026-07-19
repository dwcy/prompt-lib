import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { McpServer } from "@/api/operations";
import { useMcpServerStatus, useMcpServers } from "@/api/operations";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";

type McpStatus = McpServer["status"] | "all";

const STATUS_FILTERS: McpStatus[] = ["all", "connected", "pending", "error", "inactive"];

export function McpModule() {
  const query = useMcpServers();
  const queryClient = useQueryClient();
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [status, setStatus] = useState<McpStatus>("all");
  const [scope, setScope] = useState("all");
  const [search, setSearch] = useState("");
  const [disableCandidate, setDisableCandidate] = useState<McpServer | null>(null);
  const activateGlobal = useAction("mcp.activate_global");
  const activateLocal = useAction("mcp.activate_local");
  const approve = useAction("mcp.approve");
  const disable = useAction("mcp.disable");

  useEffect(() => {
    const succeeded = [activateGlobal, activateLocal, approve, disable].some(
      (action) => action.phase === "succeeded",
    );
    if (!succeeded) return;
    queryClient.invalidateQueries({ queryKey: ["cabal", "global", "mcp"] });
    activateGlobal.reset();
    activateLocal.reset();
    approve.reset();
    disable.reset();
  }, [activateGlobal, activateLocal, approve, disable, queryClient]);

  const rows = query.data?.servers ?? [];
  const scopes = useMemo(() => [...new Set(rows.flatMap((row) => row.scopes))].sort(), [rows]);
  const visible = useMemo(
    () =>
      rows.filter((row) => {
        const matchesStatus = status === "all" || row.status === status;
        const matchesScope = scope === "all" || row.scopes.includes(scope);
        const needle = search.trim().toLowerCase();
        const matchesSearch =
          needle.length === 0 ||
          row.name.toLowerCase().includes(needle) ||
          row.command.toLowerCase().includes(needle);
        return matchesStatus && matchesScope && matchesSearch;
      }),
    [rows, scope, search, status],
  );
  const selected = rows.find((row) => row.name === selectedName) ?? visible[0] ?? null;
  const selectedStatus = useMcpServerStatus(selected?.name ?? null);
  const inspectedServer = selectedStatus.data?.server ?? selected;

  useEffect(() => {
    if (selectedName !== null && rows.some((row) => row.name === selectedName)) return;
    setSelectedName(visible[0]?.name ?? null);
  }, [rows, selectedName, visible]);

  if (query.isPending) return <EmptyState title="Loading MCP connectors..." />;
  if (query.isError)
    return <EmptyState title="Could not load MCP connectors" body={query.error.message} />;

  return (
    <div className="mcp-workspace">
      <section className="mcp-command-center">
        <div>
          <span className="us3-eyebrow">Connector scopes</span>
          <h1>MCP Connectors</h1>
          <p>
            Every local, project, plugin, template, and remote connector is shown in one scoped
            control surface.
          </p>
        </div>
        <div className="mcp-command-center__metrics">
          <Metric label="total" value={String(query.data.counts.total)} />
          <Metric label="connected" value={String(query.data.counts.connected)} />
          <Metric label="pending" value={String(query.data.counts.pending)} />
          <Metric label="attention" value={String(query.data.counts.error)} />
        </div>
      </section>

      <section className="mcp-board">
        <div className="mcp-filter-rail">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search connector or command"
            aria-label="Search MCP connectors"
          />
          <div className="mcp-filter-rail__group">
            {STATUS_FILTERS.map((item) => (
              <button
                key={item}
                type="button"
                className={status === item ? "is-active" : undefined}
                aria-pressed={status === item}
                onClick={() => setStatus(item)}
              >
                {item}
              </button>
            ))}
          </div>
          <select
            value={scope}
            aria-label="Filter MCP connectors by scope"
            onChange={(event) => setScope(event.target.value)}
          >
            <option value="all">All scopes</option>
            {scopes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <span>{visible.length} visible</span>
        </div>

        <div className="mcp-server-stack">
          {visible.length === 0 ? (
            <EmptyState title="No connectors match these filters" />
          ) : (
            visible.map((server) => (
              <button
                key={server.name}
                type="button"
                className={`mcp-server-row${selected?.name === server.name ? " is-active" : ""}`}
                aria-pressed={selected?.name === server.name}
                onClick={() => setSelectedName(server.name)}
              >
                <span>
                  <strong>{server.name}</strong>
                  <small>{server.command || "No command recorded"}</small>
                </span>
                <span className="mcp-server-row__scope-map">
                  {scopes.map((item) => (
                    <span
                      key={item}
                      className={server.scopes.includes(item) ? "is-present" : ""}
                      title={item}
                    >
                      {item.slice(0, 1).toLocaleUpperCase()}
                    </span>
                  ))}
                </span>
                <StatePill variant={mcpVariant(server.status)} label={server.status} />
              </button>
            ))
          )}
        </div>

        <McpInspector
          server={inspectedServer}
          refreshing={selectedStatus.isFetching}
          onRecheck={() => void selectedStatus.refetch()}
          onActivateGlobal={(server) => activateGlobal.prepare({ name: server.name })}
          onActivateLocal={(server) => activateLocal.prepare({ name: server.name })}
          onApprove={(server) => approve.prepare({ name: server.name })}
          onDisable={(server) => {
            if (server.removable_scopes.length > 1) {
              setDisableCandidate(server);
              return;
            }
            disable.prepare({ name: server.name, scope: server.removable_scopes[0] ?? null });
          }}
        />
      </section>

      {disableCandidate !== null ? (
        <div
          className="mcp-scope-dialog-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="mcp-scope-dialog-title"
        >
          <section className="mcp-scope-dialog">
            <header>
              <div>
                <span className="us3-eyebrow">Connector ownership</span>
                <h2 id="mcp-scope-dialog-title">Remove one {disableCandidate.name} scope</h2>
                <p>
                  The connector can exist in several configuration layers. Removing one layer leaves
                  every other owner intact.
                </p>
              </div>
              <StatePill variant="degraded" label={`${disableCandidate.scopes.length} scopes`} />
            </header>

            <div className="mcp-scope-removal-map">
              {disableCandidate.scopes.map((item, index) => {
                const removable = disableCandidate.removable_scopes.includes(item);
                return (
                  <div key={item} className={removable ? "is-removable" : "is-retained"}>
                    <span className="mcp-scope-removal-map__step">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="mcp-scope-removal-map__identity">
                      <strong>{item}</strong>
                      <small>{scopeImpactCopy(item)}</small>
                    </span>
                    <StatePill
                      variant={removable ? "degraded" : "ok"}
                      label={removable ? "removable" : "retained"}
                    />
                    {removable ? (
                      <button
                        type="button"
                        className="danger-button"
                        onClick={() => {
                          disable.prepare({ name: disableCandidate.name, scope: item });
                          setDisableCandidate(null);
                        }}
                      >
                        Remove this scope
                      </button>
                    ) : (
                      <span className="mcp-scope-removal-map__locked">Managed elsewhere</span>
                    )}
                  </div>
                );
              })}
            </div>

            <footer>
              <span>
                A prepared confirmation will show the exact configuration file changed by the
                selected ownership layer.
              </span>
              <button type="button" onClick={() => setDisableCandidate(null)}>
                Keep all scopes
              </button>
            </footer>
          </section>
        </div>
      ) : null}

      <ActionDialog title="Activate MCP Globally" action={activateGlobal} />
      <ActionDialog title="Activate MCP Locally" action={activateLocal} />
      <ActionDialog title="Approve MCP Connector" action={approve} />
      <ActionDialog title="Disable MCP Connector" action={disable} />
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

interface McpInspectorProps {
  server: McpServer | null;
  refreshing: boolean;
  onRecheck: () => void;
  onActivateGlobal: (server: McpServer) => void;
  onActivateLocal: (server: McpServer) => void;
  onApprove: (server: McpServer) => void;
  onDisable: (server: McpServer) => void;
}

function McpInspector({
  server,
  refreshing,
  onRecheck,
  onActivateGlobal,
  onActivateLocal,
  onApprove,
  onDisable,
}: McpInspectorProps) {
  if (server === null)
    return (
      <aside className="mcp-inspector">
        <EmptyState title="Select a connector" />
      </aside>
    );
  return (
    <aside className="mcp-inspector">
      <header className="mcp-inspector__header">
        <div>
          <span className="us3-eyebrow">Scope inspector</span>
          <h2>{server.name}</h2>
        </div>
        <button type="button" onClick={onRecheck} disabled={refreshing}>
          {refreshing ? "Checking" : "Recheck"}
        </button>
      </header>
      <div className="mcp-connection-line">
        <StatePill variant={mcpVariant(server.status)} label={server.status} />
        <span>{server.active ? "active configuration" : "available configuration"}</span>
      </div>
      <div className="scope-chip-row">
        {server.scopes.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
      <pre>{server.command || "No command recorded"}</pre>
      <div className="mcp-env-grid">
        {server.env_status.length === 0 ? (
          <span>No required environment variables</span>
        ) : (
          server.env_status.map((item) => (
            <span key={item.name} className={item.present ? "is-ok" : "is-missing"}>
              <code>{item.name}</code>
              <strong>{item.present ? "ready" : "missing"}</strong>
            </span>
          ))
        )}
      </div>
      <div className="mcp-action-grid">
        <button
          type="button"
          disabled={!server.actions_available.includes("activate_global")}
          onClick={() => onActivateGlobal(server)}
        >
          {server.global_action_label}
        </button>
        <button
          type="button"
          disabled={!server.actions_available.includes("activate_local")}
          onClick={() => onActivateLocal(server)}
        >
          Activate locally
        </button>
        <button
          type="button"
          disabled={!server.actions_available.includes("approve")}
          onClick={() => onApprove(server)}
        >
          Approve
        </button>
        <button
          type="button"
          className="danger-button"
          disabled={!server.actions_available.includes("disable")}
          onClick={() => onDisable(server)}
        >
          Disable
        </button>
      </div>
    </aside>
  );
}

function ActionDialog({ title, action }: { title: string; action: ReturnType<typeof useAction> }) {
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

function mcpVariant(status: McpServer["status"]): StatePillVariant {
  switch (status) {
    case "connected":
      return "ok";
    case "pending":
      return "degraded";
    case "inactive":
      return "unavailable";
    case "error":
      return "error";
  }
}

function scopeImpactCopy(scope: string) {
  const normalized = scope.toLowerCase();
  if (normalized.includes("local") || normalized.includes("project")) {
    return "Owned by the active project; other workspaces are unaffected.";
  }
  if (normalized.includes("global") || normalized.includes("user")) {
    return "Owned by the user profile and inherited by every project.";
  }
  if (normalized.includes("plugin")) {
    return "Provided by an installed plugin and governed by that plugin lifecycle.";
  }
  if (normalized.includes("template")) {
    return "Declared by a reusable template rather than the current project.";
  }
  if (normalized.includes("remote") || normalized.includes("managed")) {
    return "Controlled outside this local workspace and retained here as reference.";
  }
  return "An independent configuration owner for this connector.";
}
