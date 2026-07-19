import { useQueryClient } from "@tanstack/react-query";
import { type CSSProperties, useEffect, useMemo, useState } from "react";
import {
  type SessionDetail,
  type SessionSummary,
  type SessionsPayload,
  useSessionDetail,
  useSessions,
} from "@/api/observability";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";

type SessionSort = "date_desc" | "cost_desc" | "tokens_desc" | "duration_desc";
type SessionLens = "all" | "errors" | "writes" | "agents";
type DetailTab = SessionDetail["tab"];

const SORTS: Array<{ value: SessionSort; label: string }> = [
  { value: "date_desc", label: "Recent" },
  { value: "cost_desc", label: "Cost" },
  { value: "tokens_desc", label: "Tokens" },
  { value: "duration_desc", label: "Duration" },
];

const TABS: DetailTab[] = ["overview", "activity", "raw", "triggers"];

export function SessionsModule() {
  const [sort, setSort] = useState<SessionSort>("date_desc");
  const [cursor, setCursor] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<DetailTab>("overview");
  const [lens, setLens] = useState<SessionLens>("all");
  const sessionsQuery = useSessions(sort, cursor);
  const detailQuery = useSessionDetail(selectedId, tab);
  const deleteAction = useAction("sessions.delete");
  const queryClient = useQueryClient();

  useEffect(() => {
    if (deleteAction.phase !== "succeeded") return;
    queryClient.invalidateQueries({ queryKey: ["cabal"] });
    setSelectedId(null);
    deleteAction.reset();
  }, [deleteAction, queryClient]);

  const visibleSessions = useMemo(
    () =>
      (sessionsQuery.data?.items ?? []).filter((session) => {
        if (lens === "errors") return session.tool_error_count > 0;
        if (lens === "writes") return session.files_written > 0;
        if (lens === "agents") return session.agent_count > 0;
        return true;
      }),
    [lens, sessionsQuery.data],
  );

  const selected = useMemo(
    () => visibleSessions.find((item) => item.session_id === selectedId) ?? null,
    [selectedId, visibleSessions],
  );

  useEffect(() => {
    if (selected !== null || visibleSessions[0] === undefined) return;
    setSelectedId(visibleSessions[0].session_id);
  }, [selected, visibleSessions]);

  if (sessionsQuery.isPending) {
    return <EmptyState title="Loading session ledger…" />;
  }

  if (sessionsQuery.isError) {
    return <EmptyState title="Could not load sessions" body={sessionsQuery.error.message} />;
  }

  const data = sessionsQuery.data;
  const active = selected ?? visibleSessions[0] ?? null;
  const lensCounts = sessionLensCounts(data.items);
  const comparisonMax = Math.max(
    1,
    ...visibleSessions.map((session) => comparisonValue(session, sort)),
  );

  return (
    <div className="sessions-workspace">
      <SessionControlTower data={data} />

      <section className="sessions-board">
        <div className="sessions-list">
          <div className="sessions-list__toolbar">
            <div>
              <span className="us3-eyebrow">Transcript ledger</span>
              <strong>{visibleSessions.length} visible sessions</strong>
            </div>
            <div className="sessions-list__toolbar-controls">
              <fieldset className="segmented-control">
                <legend className="visually-hidden">Filter sessions</legend>
                {(["all", "errors", "writes", "agents"] as SessionLens[]).map((item) => (
                  <button
                    key={item}
                    type="button"
                    className={lens === item ? "is-active" : undefined}
                    aria-pressed={lens === item}
                    onClick={() => setLens(item)}
                  >
                    {item} {lensCounts[item]}
                  </button>
                ))}
              </fieldset>
              <fieldset className="segmented-control">
                <legend className="visually-hidden">Sort sessions</legend>
                {SORTS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    className={sort === item.value ? "is-active" : undefined}
                    aria-pressed={sort === item.value}
                    onClick={() => {
                      setCursor(null);
                      setSort(item.value);
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </fieldset>
            </div>
          </div>

          {visibleSessions.length === 0 ? (
            <EmptyState
              title={
                data.items.length === 0 ? "No Claude sessions found" : "No sessions in this lens"
              }
              body={
                data.items.length === 0
                  ? "Transcript history is empty."
                  : "Choose another attention lens to widen the ledger."
              }
            />
          ) : (
            <div className="sessions-list__rows">
              {visibleSessions.map((session) => {
                const depth = sessionDepth(session, visibleSessions);
                const attention =
                  session.tool_error_count > 0
                    ? `${session.tool_error_count} tool errors`
                    : `${session.files_written} writes`;
                const intensity =
                  sort === "date_desc"
                    ? 0
                    : Math.round((comparisonValue(session, sort) / comparisonMax) * 100);
                const rowStyle = {
                  "--session-intensity": `${String(intensity)}%`,
                } as CSSProperties;
                return (
                  <button
                    type="button"
                    key={session.session_id}
                    className={`session-row session-row--depth-${Math.min(depth, 2)}${active?.session_id === session.session_id ? " is-active" : ""}`}
                    style={rowStyle}
                    aria-pressed={active?.session_id === session.session_id}
                    onClick={() => setSelectedId(session.session_id)}
                  >
                    <span className="session-row__main">
                      <strong>{session.title || compactId(session.session_id)}</strong>
                      <span className="session-row__context">
                        <span>{session.project}</span>
                        <time dateTime={session.started_at ?? undefined}>
                          {formatSessionTime(session.started_at)}
                        </time>
                        {session.parent_id !== null ? <span>child run</span> : null}
                      </span>
                    </span>
                    <span className="session-row__metrics">
                      <span>{formatDuration(session.duration_seconds)}</span>
                      <span>{formatTokens(session.tokens_in + session.tokens_out)}</span>
                      <span>{formatMoney(session.cost_usd)}</span>
                      <StatePill
                        variant={
                          session.tool_error_count > 0
                            ? "error"
                            : session.files_written > 0
                              ? "degraded"
                              : "ok"
                        }
                        label={attention}
                      />
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          <div className="sessions-list__pager">
            <button type="button" onClick={() => setCursor(null)} disabled={cursor === null}>
              First
            </button>
            <button
              type="button"
              onClick={() => setCursor(data.next_cursor)}
              disabled={data.next_cursor === null}
            >
              Next
            </button>
          </div>
        </div>

        <div className="session-inspector">
          {active === null ? (
            <EmptyState title="Select a session" />
          ) : (
            <>
              <div className="session-inspector__header">
                <div>
                  <span className="us3-eyebrow">Session detail</span>
                  <h2>{active.title || compactId(active.session_id)}</h2>
                  <p>{active.branch ?? "No branch recorded"}</p>
                </div>
                <button
                  type="button"
                  className="danger-button"
                  onClick={() => deleteAction.prepare({ session_id: active.session_id })}
                >
                  Delete
                </button>
              </div>

              <fieldset className="session-inspector__tabs">
                <legend className="visually-hidden">Session detail tabs</legend>
                {TABS.map((item) => (
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

              {detailQuery.isPending ? (
                <EmptyState title="Loading session tab…" />
              ) : detailQuery.isError ? (
                <EmptyState title="Could not load session tab" body={detailQuery.error.message} />
              ) : detailQuery.data !== undefined ? (
                <SessionTabView session={active} detail={detailQuery.data} />
              ) : null}
            </>
          )}
        </div>
      </section>

      <ConfirmDialog
        isOpen={deleteAction.phase !== "idle" && deleteAction.phase !== "succeeded"}
        actionTitle="Delete Session Transcript"
        ticket={deleteAction.ticket}
        phase={deleteAction.phase}
        reviewNotice={deleteAction.reviewNotice}
        error={deleteAction.error}
        onConfirm={deleteAction.confirm}
        onCancel={deleteAction.reset}
      />
    </div>
  );
}

function SessionControlTower({ data }: { data: SessionsPayload }) {
  const totals = data.totals;
  const rows = [
    { label: "sessions", value: String(totals.session_count) },
    { label: "tokens", value: formatTokens(totals.tokens_in + totals.tokens_out) },
    { label: "cost", value: formatMoney(totals.cost_usd) },
    { label: "writes", value: String(totals.files_written) },
  ];
  return (
    <section className="observability-hero">
      <div>
        <span className="us3-eyebrow">Usage observatory</span>
        <h1>Session command history</h1>
        <p>
          Costs, tools, subagents, write activity, and raw transcripts stay tied to the selected
          project context.
        </p>
      </div>
      <div className="observability-hero__metrics">
        {rows.map((row) => (
          <span key={row.label}>
            <strong>{row.value}</strong>
            <small>{row.label}</small>
          </span>
        ))}
      </div>
      <TokenComposition data={data} />
    </section>
  );
}

function TokenComposition({ data }: { data: SessionsPayload }) {
  const totals = data.totals;
  const parts = [
    { label: "input", value: totals.tokens_in, tone: "input" },
    { label: "output", value: totals.tokens_out, tone: "output" },
    { label: "cache read", value: totals.cache_read_tokens, tone: "cache-read" },
    { label: "cache write", value: totals.cache_write_tokens, tone: "cache-write" },
  ];
  const total = Math.max(
    1,
    parts.reduce((sum, part) => sum + part.value, 0),
  );
  return (
    <div className="token-composition">
      <div className="token-composition__header">
        <span>Token composition</span>
        <strong>{formatTokens(total)}</strong>
      </div>
      <div className="token-composition__bar">
        {parts.map((part) => (
          <span
            key={part.label}
            className={`token-composition__segment token-composition__segment--${part.tone}`}
            style={{ flexGrow: part.value }}
            title={`${part.label}: ${part.value.toLocaleString()}`}
          />
        ))}
      </div>
      <div className="token-composition__legend">
        {parts.map((part) => (
          <span key={part.label} data-tone={part.tone}>
            <i />
            {part.label} <strong>{formatTokens(part.value)}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

function SessionTabView({ session, detail }: { session: SessionSummary; detail: SessionDetail }) {
  if (detail.tab === "overview") {
    const models = arrayFrom(detail.payload.models);
    return (
      <div className="session-overview">
        <div className="session-tab-grid">
          <MetricTile label="duration" value={formatDuration(session.duration_seconds)} />
          <MetricTile label="messages" value={String(session.message_count)} />
          <MetricTile label="agents" value={String(session.agent_count)} />
          <MetricTile label="tool errors" value={String(session.tool_error_count)} />
        </div>
        <div className="session-activity-fingerprint">
          <span>
            <small>skills</small>
            <strong>{session.skill_count}</strong>
          </span>
          <span>
            <small>tools</small>
            <strong>{session.tool_count}</strong>
          </span>
          <span>
            <small>hooks</small>
            <strong>{session.hook_count}</strong>
          </span>
          <span>
            <small>files written</small>
            <strong>{session.files_written}</strong>
          </span>
        </div>
        <div className="session-model-stack">
          {models.map((model) => (
            <span key={String(model.model)}>
              <strong>{String(model.model)}</strong>
              <small>
                {formatTokens(numberValue(model.tokens_in) + numberValue(model.tokens_out))}
              </small>
            </span>
          ))}
        </div>
      </div>
    );
  }

  if (detail.tab === "raw") {
    return <pre className="session-raw-log">{String(detail.payload.text ?? "")}</pre>;
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
      <div className="session-activity-groups">
        {groups.map((group) => (
          <section key={group.label} className="session-activity-group">
            <header>
              <strong>{group.label}</strong>
              <span>{group.rows.length}</span>
            </header>
            <SessionEventRows tab={detail.tab} rows={group.rows} />
          </section>
        ))}
      </div>
    );
  }

  const rows = arrayFrom(detail.payload.events);
  return (
    <div className="session-event-stack">
      {rows.length === 0 ? (
        <EmptyState title={`No ${detail.tab} entries`} />
      ) : (
        <SessionEventRows tab={detail.tab} rows={rows} />
      )}
    </div>
  );
}

function SessionEventRows({ tab, rows }: { tab: DetailTab; rows: Array<Record<string, unknown>> }) {
  return rows.slice(0, 80).map((row) => (
    <div className="session-event-row" key={`${tab}-${eventKey(row)}`}>
      <strong>
        {String(row.tool_name ?? row.tool ?? row.skill_name ?? row.agent_type ?? "event")}
      </strong>
      <span>{String(row.input_preview ?? row.path ?? row.description ?? row.args ?? "")}</span>
    </div>
  ));
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <span className="metric-tile">
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

function compactId(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

function formatTokens(value: number) {
  return Intl.NumberFormat(undefined, { notation: "compact" }).format(value);
}

function formatMoney(value: number) {
  return Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(value);
}

function formatDuration(value: number) {
  if (value < 60) return `${Math.round(value)}s`;
  return `${Math.round(value / 60)}m`;
}

function formatSessionTime(value: string | null) {
  if (value === null) return "time unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sessionDepth(session: SessionSummary, sessions: SessionSummary[]) {
  let depth = 0;
  let parentId = session.parent_id;
  const visited = new Set<string>();
  while (parentId !== null && depth < 3 && !visited.has(parentId)) {
    visited.add(parentId);
    const parent = sessions.find((candidate) => candidate.session_id === parentId);
    if (parent === undefined) break;
    depth += 1;
    parentId = parent.parent_id;
  }
  return depth;
}

function sessionLensCounts(sessions: SessionSummary[]): Record<SessionLens, number> {
  return {
    all: sessions.length,
    errors: sessions.filter((session) => session.tool_error_count > 0).length,
    writes: sessions.filter((session) => session.files_written > 0).length,
    agents: sessions.filter((session) => session.agent_count > 0).length,
  };
}

function comparisonValue(session: SessionSummary, sort: SessionSort) {
  if (sort === "cost_desc") return session.cost_usd;
  if (sort === "tokens_desc") return session.tokens_in + session.tokens_out;
  if (sort === "duration_desc") return session.duration_seconds;
  return 0;
}

function arrayFrom(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> => typeof item === "object" && item !== null,
      )
    : [];
}

function numberValue(value: unknown) {
  return typeof value === "number" ? value : 0;
}

function eventKey(row: Record<string, unknown>) {
  return String(
    row.timestamp ??
      row.tool_name ??
      row.tool ??
      row.skill_name ??
      row.agent_type ??
      row.path ??
      JSON.stringify(row),
  );
}
