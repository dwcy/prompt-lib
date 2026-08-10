// Sessions & cost module: console cost-table layout — totals KPI row, virtualized session
// table with cost-share bars, sticky detail drawer, lazy detail tabs, and guarded delete.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSessions } from "@/api/observability";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { useAction } from "@/hooks/useAction";
import { SessionDetailPanel } from "./components/SessionDetailPanel";
import { SessionDrawer } from "./components/SessionDrawer";
import { SessionsTable } from "./components/SessionsTable";
import { SessionsTotals } from "./components/SessionsTotals";
import {
  type SessionLens,
  type SessionSort,
  sessionLensCounts,
  sessionMatchesLens,
} from "./sessionsPresentation";
import "./SessionsModule.css";

const SESSIONS_ROOT = "~/.claude/projects";

export function SessionsModule() {
  const [sort, setSort] = useState<SessionSort>("date_desc");
  const [cursor, setCursor] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [lens, setLens] = useState<SessionLens>("all");
  const sessionsQuery = useSessions(sort, cursor);
  const deleteAction = useAction("sessions.delete");
  const queryClient = useQueryClient();

  useEffect(() => {
    if (deleteAction.phase !== "succeeded") return;
    queryClient.invalidateQueries({ queryKey: ["cabal"] });
    setSelectedId(null);
    deleteAction.reset();
  }, [deleteAction, queryClient]);

  const visibleSessions = useMemo(
    () => (sessionsQuery.data?.items ?? []).filter((session) => sessionMatchesLens(session, lens)),
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
  const maxCost = visibleSessions.reduce((max, session) => Math.max(max, session.cost_usd), 0);
  const sourceHint = data.project === null ? SESSIONS_ROOT : `${SESSIONS_ROOT} · ${data.project}`;

  return (
    <div className="sess-module">
      <SessionsTotals totals={data.totals} />

      <div className="sess-layout">
        <div className="sess-main">
          <SessionsTable
            sessions={visibleSessions}
            activeId={active?.session_id ?? null}
            onSelect={setSelectedId}
            lens={lens}
            lensCounts={sessionLensCounts(data.items)}
            onLensChange={setLens}
            sort={sort}
            onSortChange={(next) => {
              setCursor(null);
              setSort(next);
            }}
            sourceHint={sourceHint}
            maxCost={maxCost}
            hasAnyItems={data.items.length > 0}
            isFirstPage={cursor === null}
            hasNextPage={data.next_cursor !== null}
            onFirstPage={() => setCursor(null)}
            onNextPage={() => setCursor(data.next_cursor)}
          />
          {active !== null ? <SessionDetailPanel session={active} /> : null}
        </div>

        {active !== null ? (
          <SessionDrawer
            session={active}
            onDelete={() => deleteAction.prepare({ session_id: active.session_id })}
          />
        ) : (
          <aside className="sess-drawer" aria-label="Selected session detail">
            <EmptyState title="Select a session" />
          </aside>
        )}
      </div>

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
