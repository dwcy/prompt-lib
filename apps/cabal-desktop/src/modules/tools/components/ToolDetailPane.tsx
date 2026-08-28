// Sticky detail pane (third console pane): tool identity + status pill, description, badge chips,
// mono fact rows, safety notes, source-doc link, and the install/update action flow (T042/T043).
import { type ToolDetail, useToolDetail } from "@/api/tools";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { ToolActionPanel } from "@/modules/tools/actions";
import {
  formatCheckedAt,
  formatInstallChannel,
  toStatePillVariant,
} from "@/modules/tools/toolStatusPresentation";

export interface ToolDetailPaneProps {
  toolKey: string | null;
}

export function ToolDetailPane({ toolKey }: ToolDetailPaneProps) {
  const detailQuery = useToolDetail(toolKey);
  return (
    <aside className="tools-console__detail" aria-label="Tool detail">
      {toolKey === null ? (
        <EmptyState title="No tool selected" body="Pick a row to inspect a tool." />
      ) : detailQuery.isPending ? (
        <EmptyState title="Loading tool detail" animated />
      ) : detailQuery.isError ? (
        <EmptyState title="Could not load tool detail" body={detailQuery.error.message} />
      ) : detailQuery.data !== undefined ? (
        <ToolDetailBody tool={detailQuery.data} />
      ) : null}
    </aside>
  );
}

interface ToolDetailBodyProps {
  tool: ToolDetail;
}

function ToolDetailBody({ tool }: ToolDetailBodyProps) {
  const facts = [
    { label: "category", value: tool.category },
    { label: "channel", value: formatInstallChannel(tool.install_channel) },
    { label: "source", value: tool.source_state },
    { label: "platforms", value: tool.platforms.length > 0 ? tool.platforms.join(", ") : "—" },
    { label: "current", value: tool.status.current_version ?? "not installed" },
    { label: "latest", value: tool.status.latest_version ?? "not reported" },
    { label: "checked", value: formatCheckedAt(tool.status.checked_at) },
    { label: "backup policy", value: tool.backup_policy ?? "none" },
  ];

  return (
    <>
      <div className="tools-console__detail-header select-none">
        <h3>{tool.label}</h3>
        <StatePill variant={toStatePillVariant(tool.status.state)} />
      </div>

      <p className="tools-console__detail-description">{tool.description}</p>

      {tool.badges.length > 0 ? (
        <ul className="tools-console__detail-badges select-none">
          {tool.badges.map((badge) => (
            <li key={badge}>{badge}</li>
          ))}
        </ul>
      ) : null}

      <dl className="tools-console__facts">
        {facts.map((fact) => (
          <div key={fact.label} className="tools-console__fact">
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>

      {tool.safety_notes.length > 0 ? (
        <ul className="tools-console__safety-notes">
          {tool.safety_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}

      {tool.source_url !== null ? (
        <a
          className="tools-console__source-link"
          href={tool.source_url}
          target="_blank"
          rel="noreferrer"
        >
          Source documentation →
        </a>
      ) : null}

      <ToolActionPanel key={tool.key} tool={tool} />
    </>
  );
}
