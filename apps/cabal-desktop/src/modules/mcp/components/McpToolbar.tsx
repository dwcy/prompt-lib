// Filter toolbar above the connectors table: free-text search (name/command), status chip filters,
// and a scope <select> — unchanged filtering behavior from the pre-redesign module, restyled as a
// console toolbar row.
import type { McpServer } from "@/api/operations";

export type McpStatusFilter = McpServer["status"] | "all";

export const MCP_STATUS_FILTERS: McpStatusFilter[] = [
  "all",
  "connected",
  "pending",
  "error",
  "inactive",
];

export interface McpToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  status: McpStatusFilter;
  onStatusChange: (value: McpStatusFilter) => void;
  scope: string;
  onScopeChange: (value: string) => void;
  scopes: string[];
  visibleCount: number;
}

export function McpToolbar({
  search,
  onSearchChange,
  status,
  onStatusChange,
  scope,
  onScopeChange,
  scopes,
  visibleCount,
}: McpToolbarProps) {
  return (
    <div className="mcp-toolbar">
      <input
        className="mcp-toolbar__search"
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        placeholder="Search connector or command"
        aria-label="Search MCP connectors"
      />
      <div className="mcp-toolbar__filters">
        {MCP_STATUS_FILTERS.map((item) => (
          <button
            key={item}
            type="button"
            className={status === item ? "is-active" : undefined}
            aria-pressed={status === item}
            onClick={() => onStatusChange(item)}
          >
            {item}
          </button>
        ))}
      </div>
      <select
        className="mcp-toolbar__scope"
        value={scope}
        aria-label="Filter MCP connectors by scope"
        onChange={(event) => onScopeChange(event.target.value)}
      >
        <option value="all">All scopes</option>
        {scopes.map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
      </select>
      <span className="mcp-toolbar__count">{visibleCount} visible</span>
    </div>
  );
}
