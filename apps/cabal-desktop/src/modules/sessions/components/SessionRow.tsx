// Single virtualized session row: fork glyph for subagent children, mono metrics, and the
// proportional cost-share bar (width is runtime-computed from session cost / page max cost).
import type { CSSProperties } from "react";
import type { SessionSummary } from "@/api/observability";
import { compactId, formatDuration, formatMoney, formatSessionTime } from "../sessionsPresentation";

export interface SessionRowProps {
  session: SessionSummary;
  isActive: boolean;
  sharePct: number;
  offsetY: number;
  height: number;
  onSelect: (id: string) => void;
}

export function SessionRow({
  session,
  isActive,
  sharePct,
  offsetY,
  height,
  onSelect,
}: SessionRowProps) {
  const isChild = session.parent_id !== null;
  const positionStyle: CSSProperties = { transform: `translateY(${offsetY}px)`, height };
  const branchLabel = session.branch ?? session.title ?? compactId(session.session_id);
  return (
    <button
      type="button"
      className={`sess-row${isActive ? " is-active" : ""}`}
      style={positionStyle}
      aria-pressed={isActive}
      title={session.title ?? session.session_id}
      onClick={() => onSelect(session.session_id)}
    >
      <span className="sess-row__fork" aria-hidden="true">
        {isChild ? "└" : ""}
      </span>
      <span className="sess-row__started">{formatSessionTime(session.started_at)}</span>
      <span
        className={`sess-row__branch${session.branch === null ? " sess-row__branch--fallback" : ""}`}
      >
        {branchLabel}
      </span>
      <span className="sess-row__num">{formatDuration(session.duration_seconds)}</span>
      <span className="sess-row__cost">{formatMoney(session.cost_usd)}</span>
      <span className="sess-row__share">
        <span className="sess-row__share-fill" style={{ width: `${sharePct}%` }} />
      </span>
      <span className="sess-row__count">{session.tool_count}</span>
      <span className="sess-row__count">{session.agent_count}</span>
    </button>
  );
}
