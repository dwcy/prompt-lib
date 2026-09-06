// Sessions table card: header bar with lens/sort segmented pills and mono source hint,
// uppercase column header row, virtualized session rows, and the cursor pager footer.
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";
import type { SessionSummary } from "@/api/observability";
import { EmptyState } from "@/components/EmptyState";
import {
  SESSION_LENSES,
  SESSION_SORTS,
  type SessionLens,
  type SessionSort,
} from "../sessionsPresentation";
import { SessionRow } from "./SessionRow";

const ROW_HEIGHT = 34;

export interface SessionsTableProps {
  sessions: SessionSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  lens: SessionLens;
  lensCounts: Record<SessionLens, number>;
  onLensChange: (lens: SessionLens) => void;
  sort: SessionSort;
  onSortChange: (sort: SessionSort) => void;
  sourceHint: string;
  maxCost: number;
  hasAnyItems: boolean;
  isFirstPage: boolean;
  hasNextPage: boolean;
  onFirstPage: () => void;
  onNextPage: () => void;
}

export function SessionsTable({
  sessions,
  activeId,
  onSelect,
  lens,
  lensCounts,
  onLensChange,
  sort,
  onSortChange,
  sourceHint,
  maxCost,
  hasAnyItems,
  isFirstPage,
  hasNextPage,
  onFirstPage,
  onNextPage,
}: SessionsTableProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: sessions.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  return (
    <section className="sess-card" aria-label="Sessions cost table">
      <div className="sess-table__bar">
        <b className="sess-table__title">Sessions</b>
        <fieldset className="sess-pills">
          <legend className="sess-vh">Filter sessions</legend>
          {SESSION_LENSES.map((item) => (
            <button
              key={item}
              type="button"
              className={lens === item ? "is-active" : undefined}
              aria-pressed={lens === item}
              onClick={() => onLensChange(item)}
            >
              {item} · {lensCounts[item]}
            </button>
          ))}
        </fieldset>
        <fieldset className="sess-pills">
          <legend className="sess-vh">Sort sessions</legend>
          {SESSION_SORTS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={sort === item.value ? "is-active" : undefined}
              aria-pressed={sort === item.value}
              onClick={() => onSortChange(item.value)}
            >
              {item.label}
            </button>
          ))}
        </fieldset>
        <span className="sess-table__source">{sourceHint}</span>
      </div>

      <div className="sess-table__head">
        <span />
        <span>Started</span>
        <span>Branch</span>
        <span className="sess-num">Dur</span>
        <span className="sess-num">Cost</span>
        <span>Cost share</span>
        <span className="sess-num">Tools</span>
        <span className="sess-num">Agents</span>
      </div>

      {sessions.length === 0 ? (
        <EmptyState
          title={hasAnyItems ? "No sessions in this lens" : "No Claude sessions found"}
          body={
            hasAnyItems
              ? "Choose another attention lens to widen the ledger."
              : "Transcript history is empty."
          }
        />
      ) : (
        <div className="sess-table__body" ref={scrollRef}>
          {/* Total height is runtime-computed by the virtualizer. */}
          <div className="sess-table__rows" style={{ height: virtualizer.getTotalSize() }}>
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const session = sessions[virtualRow.index];
              return (
                <SessionRow
                  key={session.session_id}
                  session={session}
                  isActive={activeId === session.session_id}
                  sharePct={maxCost > 0 ? (session.cost_usd / maxCost) * 100 : 0}
                  offsetY={virtualRow.start}
                  height={virtualRow.size}
                  onSelect={onSelect}
                />
              );
            })}
          </div>
        </div>
      )}

      <div className="sess-table__pager">
        <button type="button" onClick={onFirstPage} disabled={isFirstPage}>
          First
        </button>
        <button type="button" onClick={onNextPage} disabled={!hasNextPage}>
          Next
        </button>
      </div>
    </section>
  );
}
