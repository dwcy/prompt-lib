// T038: drill-down into one cell's deterministic check outcomes and agent metrics (FR-042). A
// timed-out check renders as a labelled result, never as an error — the subsystem guarantees a
// check outcome cannot abort its cell (data-model A6).
import { useEvalsCellDetail } from "@/api/evals";
import { EmptyState } from "@/components/EmptyState";

export interface CellDetailProps {
  runId: string;
  task: string;
  profile: string;
  repetition: number;
  onClose: () => void;
}

export function CellDetail({ runId, task, profile, repetition, onClose }: CellDetailProps) {
  const cellQuery = useEvalsCellDetail(runId, task, profile, repetition);

  return (
    <section
      className="cell-detail"
      aria-label={`Cell detail: ${task} / ${profile} / rep ${repetition}`}
    >
      <header className="cell-detail__header select-none">
        <h2>
          {task} — {profile} — rep {repetition}
        </h2>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </header>

      {cellQuery.isPending ? <EmptyState title="Loading cell…" /> : null}
      {cellQuery.isError ? (
        <EmptyState title="Could not load this cell" body={cellQuery.error.message} />
      ) : null}

      {cellQuery.data !== undefined ? (
        <>
          <section aria-label="Checks">
            <h3>Checks</h3>
            <ul className="cell-detail__checks">
              {cellQuery.data.checks.map((check) => (
                <li
                  key={`${check.kind}-${check.exit_code ?? "none"}-${check.passed}-${check.failed}`}
                  className="cell-detail__check"
                  data-timed-out={check.timed_out}
                >
                  <span>{check.kind}</span>
                  <span>
                    {check.passed} passed / {check.failed} failed
                  </span>
                  {check.timed_out ? (
                    <span className="cell-detail__timeout-flag">timed out</span>
                  ) : null}
                  <span>exit {check.exit_code ?? "n/a"}</span>
                </li>
              ))}
            </ul>
          </section>

          <section aria-label="Agent metrics">
            <h3>Agent metrics</h3>
            <dl className="cell-detail__agent-metrics">
              <div>
                <dt>Tool calls</dt>
                <dd>{cellQuery.data.agent_metrics.tool_calls}</dd>
              </div>
              <div>
                <dt>Tokens (total)</dt>
                <dd>{cellQuery.data.agent_metrics.tokens_total}</dd>
              </div>
              <div>
                <dt>Wall time</dt>
                <dd>{cellQuery.data.agent_metrics.wall_seconds.toFixed(1)}s</dd>
              </div>
              <div>
                <dt>Unrequested changes</dt>
                <dd>{cellQuery.data.unrequested_changes}</dd>
              </div>
            </dl>
          </section>
        </>
      ) : null}
    </section>
  );
}
