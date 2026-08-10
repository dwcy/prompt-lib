// Command header: bold title, muted description of what the module manages, and a right-aligned
// mono connector count sourced from the real /api/mcp payload counts.
export interface McpHeaderProps {
  total: number;
}

export function McpHeader({ total }: McpHeaderProps) {
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
    </section>
  );
}
