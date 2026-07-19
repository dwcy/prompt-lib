// Full tool detail body: description, source link, current status, badges, safety notes, backup
// policy, and the install/update action panel (T042 detail drawer + T043 action flow).
import type { ToolDetail } from "@/api/tools";
import { StatePill } from "@/components/StatePill";
import { ToolActionPanel } from "@/modules/tools/actions";
import { toStatePillVariant } from "@/modules/tools/toolStatusPresentation";

export interface ToolDetailContentProps {
  tool: ToolDetail;
}

export function ToolDetailContent({ tool }: ToolDetailContentProps) {
  return (
    <div className="tool-detail-content">
      <p className="tool-detail-content__description">{tool.description}</p>

      {tool.source_url !== null ? (
        <p>
          <a href={tool.source_url} target="_blank" rel="noreferrer">
            Read more
          </a>
        </p>
      ) : null}

      <div className="tool-detail-content__status select-none">
        <StatePill variant={toStatePillVariant(tool.status.state)} />
        <span>Current: {tool.status.current_version ?? "—"}</span>
        <span>Latest: {tool.status.latest_version ?? "—"}</span>
      </div>

      {tool.badges.length > 0 ? (
        <ul className="tool-detail-content__badges select-none">
          {tool.badges.map((badge) => (
            <li key={badge}>{badge}</li>
          ))}
        </ul>
      ) : null}

      {tool.safety_notes.length > 0 ? (
        <ul className="tool-detail-content__safety-notes">
          {tool.safety_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}

      {tool.backup_policy !== null ? (
        <p className="tool-detail-content__backup-policy">Backup policy: {tool.backup_policy}</p>
      ) : null}

      <ToolActionPanel tool={tool} />
    </div>
  );
}
