// Session detail tabs card: overview metric tiles + model breakdown, activity groups,
// raw transcript log, and write-audit trigger events — lazy-loaded per tab.
import { useState } from "react";
import { type SessionDetail, type SessionSummary, useSessionDetail } from "@/api/observability";
import { EmptyState } from "@/components/EmptyState";
import {
  arrayFrom,
  DETAIL_TABS,
  type DetailTab,
  eventKey,
  formatDuration,
  formatMoney,
  formatTokens,
  numberValue,
  sessionTitle,
} from "../sessionsPresentation";

export interface SessionDetailPanelProps {
  session: SessionSummary;
}

export function SessionDetailPanel({ session }: SessionDetailPanelProps) {
  const [tab, setTab] = useState<DetailTab>("overview");
  const detailQuery = useSessionDetail(session.session_id, tab);

  return (
    <section className="sess-card" aria-label="Session detail tabs">
      <div className="sess-table__bar">
        <b className="sess-table__title">Detail</b>
        <fieldset className="sess-pills">
          <legend className="sess-vh">Session detail tabs</legend>
          {DETAIL_TABS.map((item) => (
            <button
              key={item}
              type="button"
              className={tab === item ? "is-active" : undefined}
              aria-pressed={tab === item}
              onClick={() => setTab(item)}
            >
              {item}
            </button>
          ))}
        </fieldset>
        <span className="sess-table__source">{sessionTitle(session)}</span>
      </div>
      <div className="sess-detail__body">
        {detailQuery.isPending ? (
          <EmptyState title="Loading session tab…" />
        ) : detailQuery.isError ? (
          <EmptyState title="Could not load session tab" body={detailQuery.error.message} />
        ) : detailQuery.data !== undefined ? (
          <TabContent session={session} detail={detailQuery.data} />
        ) : null}
      </div>
    </section>
  );
}

function TabContent({ session, detail }: { session: SessionSummary; detail: SessionDetail }) {
  if (detail.tab === "overview") {
    const metrics = [
      { label: "duration", value: formatDuration(session.duration_seconds) },
      { label: "messages", value: String(session.message_count) },
      { label: "agents", value: String(session.agent_count) },
      { label: "tool errors", value: String(session.tool_error_count) },
      { label: "skills", value: String(session.skill_count) },
      { label: "tools", value: String(session.tool_count) },
      { label: "hooks", value: String(session.hook_count) },
      { label: "files written", value: String(session.files_written) },
    ];
    const models = arrayFrom(detail.payload.models);
    return (
      <div className="sess-overview">
        <div className="sess-metric-grid">
          {metrics.map((metric) => (
            <span key={metric.label} className="sess-metric">
              <strong>{metric.value}</strong>
              <small>{metric.label}</small>
            </span>
          ))}
        </div>
        {models.length > 0 ? (
          <div>
            {models.map((model) => (
              <div key={String(model.model)} className="sess-model-row">
                <span className="sess-model-name">{String(model.model)}</span>
                <span className="sess-model-tokens">
                  {formatTokens(numberValue(model.tokens_in) + numberValue(model.tokens_out))} tok
                </span>
                <span className="sess-model-cost">{formatMoney(numberValue(model.cost_usd))}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  if (detail.tab === "raw") {
    return <pre className="sess-raw">{String(detail.payload.text ?? "")}</pre>;
  }

  if (detail.tab === "activity") {
    const groups = [
      { label: "Skills", rows: arrayFrom(detail.payload.skills) },
      { label: "Agents", rows: arrayFrom(detail.payload.agents) },
      { label: "Tools", rows: arrayFrom(detail.payload.tools) },
      { label: "Hooks", rows: arrayFrom(detail.payload.hooks) },
    ].filter((group) => group.rows.length > 0);
    return groups.length === 0 ? (
      <EmptyState title="No activity entries" />
    ) : (
      <div>
        {groups.map((group) => (
          <section key={group.label} className="sess-activity-group">
            <header>
              <strong>{group.label}</strong>
              <span>{group.rows.length}</span>
            </header>
            <EventRows tab={detail.tab} rows={group.rows} />
          </section>
        ))}
      </div>
    );
  }

  const rows = arrayFrom(detail.payload.events);
  return rows.length === 0 ? (
    <EmptyState title={`No ${detail.tab} entries`} />
  ) : (
    <div>
      <EventRows tab={detail.tab} rows={rows} />
    </div>
  );
}

const MAX_EVENT_ROWS = 80;

function EventRows({ tab, rows }: { tab: DetailTab; rows: Array<Record<string, unknown>> }) {
  return rows.slice(0, MAX_EVENT_ROWS).map((row) => (
    <div className="sess-event" key={`${tab}-${eventKey(row)}`}>
      <strong>
        {String(row.tool_name ?? row.tool ?? row.skill_name ?? row.agent_type ?? "event")}
      </strong>
      <span>{String(row.input_preview ?? row.path ?? row.description ?? row.args ?? "")}</span>
    </div>
  ));
}
