// MCP Connectors console screen: header + count, filter toolbar, the connectors table (status
// dot, scope chips, per-row actions + recheck), and the selected-connector detail panel — same
// data (/api/mcp) and confirm-flow-gated mutations as the original module, restyled as a console
// card/table per the Agents-screen dispatch scope-down (MCP servers is the one real data source).
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { McpServer } from "@/api/operations";
import { useMcpServerStatus, useMcpServers } from "@/api/operations";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { type UseActionResult, useAction } from "@/hooks/useAction";
import { McpConnectorsTable } from "@/modules/mcp/components/McpConnectorsTable";
import { McpDetailPanel } from "@/modules/mcp/components/McpDetailPanel";
import { McpHeader } from "@/modules/mcp/components/McpHeader";
import { McpScopeDialog } from "@/modules/mcp/components/McpScopeDialog";
import { type McpStatusFilter, McpToolbar } from "@/modules/mcp/components/McpToolbar";
import "./McpModule.css";

export function McpModule() {
  const query = useMcpServers();
  const queryClient = useQueryClient();
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [status, setStatus] = useState<McpStatusFilter>("all");
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
    queryClient.invalidateQueries({ queryKey: queryKeys.global("mcp") });
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

  const handleRecheck = (server: McpServer) => {
    setSelectedName(server.name);
    queryClient.invalidateQueries({ queryKey: queryKeys.global("mcp", "status", server.name) });
  };

  const handleDisable = (server: McpServer) => {
    if (server.removable_scopes.length > 1) {
      setDisableCandidate(server);
      return;
    }
    disable.prepare({ name: server.name, scope: server.removable_scopes[0] ?? null });
  };

  if (query.isPending) return <EmptyState title="Loading MCP connectors..." />;
  if (query.isError)
    return <EmptyState title="Could not load MCP connectors" body={query.error.message} />;

  return (
    <div className="mcp-console">
      <McpHeader total={query.data.counts.total} />

      <McpToolbar
        search={search}
        onSearchChange={setSearch}
        status={status}
        onStatusChange={setStatus}
        scope={scope}
        onScopeChange={setScope}
        scopes={scopes}
        visibleCount={visible.length}
      />

      <McpConnectorsTable
        servers={visible}
        selectedName={selected?.name ?? null}
        onSelect={setSelectedName}
        onRecheck={handleRecheck}
        onActivateGlobal={(server) => activateGlobal.prepare({ name: server.name })}
        onActivateLocal={(server) => activateLocal.prepare({ name: server.name })}
        onApprove={(server) => approve.prepare({ name: server.name })}
        onDisable={handleDisable}
      />

      <McpDetailPanel
        server={inspectedServer}
        refreshing={selectedStatus.isFetching}
        onRecheck={() => void selectedStatus.refetch()}
        onActivateGlobal={(server) => activateGlobal.prepare({ name: server.name })}
        onActivateLocal={(server) => activateLocal.prepare({ name: server.name })}
        onApprove={(server) => approve.prepare({ name: server.name })}
        onDisable={handleDisable}
      />

      {disableCandidate !== null ? (
        <McpScopeDialog
          candidate={disableCandidate}
          onRemoveScope={(server, scopeToRemove) => {
            disable.prepare({ name: server.name, scope: scopeToRemove });
            setDisableCandidate(null);
          }}
          onDismiss={() => setDisableCandidate(null)}
        />
      ) : null}

      <McpActionDialog title="Activate MCP Globally" action={activateGlobal} />
      <McpActionDialog title="Activate MCP Locally" action={activateLocal} />
      <McpActionDialog title="Approve MCP Connector" action={approve} />
      <McpActionDialog title="Disable MCP Connector" action={disable} />
    </div>
  );
}

function McpActionDialog({ title, action }: { title: string; action: UseActionResult }) {
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
