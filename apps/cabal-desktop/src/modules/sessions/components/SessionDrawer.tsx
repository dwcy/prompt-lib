// Sticky session detail drawer: title + mono id, fact rows, subagent dispatch rollup
// (from the lazy activity tab payload), data-source footer note, and the delete action.
import { type SessionSummary, useSessionDetail } from "@/api/observability";
import {
  aggregateDispatches,
  arrayFrom,
  compactId,
  formatDuration,
  formatMoney,
  formatTokens,
  sessionTitle,
} from "../sessionsPresentation";

export interface SessionDrawerProps {
  session: SessionSummary;
  onDelete: () => void;
}

export function SessionDrawer({ session, onDelete }: SessionDrawerProps) {
  const hasDispatches = session.agent_count > 0;
  const activityQuery = useSessionDetail(hasDispatches ? session.session_id : null, "activity");
  const dispatches =
    activityQuery.data === undefined
      ? null
      : aggregateDispatches(arrayFrom(activityQuery.data.payload.agents));

  const facts = [
    { label: "branch", value: session.branch ?? "—" },
    { label: "duration", value: formatDuration(session.duration_seconds) },
    { label: "cost", value: formatMoney(session.cost_usd) },
    {
      label: "tokens",
      value: `${formatTokens(session.tokens_in + session.tokens_out)} (${formatTokens(session.tokens_in)} in · ${formatTokens(session.tokens_out)} out)`,
    },
    { label: "tool calls", value: String(session.tool_count) },
  ];

  return (
    <aside className="sess-drawer" aria-label="Selected session detail">
      <div className="sess-drawer__head">
        <b className="sess-drawer__title">{sessionTitle(session)}</b>
        <span className="sess-drawer__id">{compactId(session.session_id)}</span>
      </div>

      <dl className="sess-facts">
        {facts.map((fact) => (
          <div key={fact.label}>
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>

      {hasDispatches ? (
        <>
          <div className="sess-drawer__section">Subagent dispatches</div>
          {activityQuery.isPending ? (
            <p className="sess-drawer__pending">Loading dispatches…</p>
          ) : activityQuery.isError ? (
            <p className="sess-drawer__pending">Could not load dispatch activity.</p>
          ) : dispatches !== null && dispatches.length > 0 ? (
            <div className="sess-dispatches">
              {dispatches.map((row) => (
                <div key={row.name} className="sess-dispatch">
                  <span className="sess-dispatch__name">{row.name}</span>
                  <span className="sess-dispatch__calls">{row.calls}×</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="sess-drawer__pending">No dispatch entries recorded.</p>
          )}
        </>
      ) : null}

      <p className="sess-drawer__note">
        Costs estimated from token usage in ~/.claude/projects JSONL transcripts; dispatch rows
        are Task-tool invocations.
      </p>

      <div className="sess-drawer__actions">
        <button type="button" className="sess-danger-btn" onClick={onDelete}>
          Delete session
        </button>
      </div>
    </aside>
  );
}
