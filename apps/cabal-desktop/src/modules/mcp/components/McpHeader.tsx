// Command header: bold title, muted description of what the module manages, and a right-aligned
// mono connector count sourced from the real /api/mcp payload counts.
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { RefreshButton } from "@/components/RefreshButton";

export interface McpHeaderProps {
  total: number;
  onRefresh: () => void;
  isFetching: boolean;
}

export function McpHeader({ total, onRefresh, isFetching }: McpHeaderProps) {
  return (
    <section className="mcp-header">
      <div className="mcp-header__intro">
        <span className="mcp-eyebrow">Connector scopes</span>
        <h1>MCP Connectors</h1>
        <p>
          Every local, project, plugin, template, and remote connector is shown in one scoped
          control surface.
        </p>
      </div>
      <span className="mcp-header__count">
        {total} connector{total === 1 ? "" : "s"}
      </span>
      <CardRefreshFooter>
        <RefreshButton label="connectors" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </section>
  );
}
