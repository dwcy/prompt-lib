// T037 support: the pairwise judge's per-pair verdicts, and how many pairs were excluded from the
// win rate and why (FR-039). The win rate itself renders from the metric the backend already
// computed (MetricsTable's pairwise_win_rate row) — this component tallies nothing.
import type { EvalsPairwiseExclusion, EvalsVerdict } from "@/api/evals";

export interface VerdictSummaryProps {
  verdicts: EvalsVerdict[];
  excluded: EvalsPairwiseExclusion;
}

type DisplayedOutcome = "baseline" | "candidate" | "tie" | "error";

export function VerdictSummary({ verdicts, excluded }: VerdictSummaryProps) {
  return (
    <section className="verdict-summary" aria-label="Judge verdicts">
      <h2>Judge verdicts</h2>
      <p className="verdict-summary__exclusions" role="note">
        {excluded.ties} pair{excluded.ties === 1 ? "" : "s"} excluded as ties and{" "}
        {excluded.judge_errors} excluded for judge errors — the win rate above counts neither.
      </p>
      <ul className="verdict-summary__list">
        {verdicts.map((verdict) => (
          <li
            key={`${verdict.task}-${verdict.repetition}`}
            className="verdict-summary__item"
            data-outcome={displayedOutcome(verdict)}
          >
            <code>{verdict.task}</code>
            <span>rep {verdict.repetition}</span>
            <span>{describeOutcome(verdict)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function displayedOutcome(verdict: EvalsVerdict): DisplayedOutcome {
  if (verdict.judge_error) return "error";
  // FR-038: order disagreement is always a tie, regardless of `winner` — never a win, even if the
  // payload's `winner` field disagrees. Redundant with the backend contract, on purpose.
  if (!verdict.order_agreement) return "tie";
  return verdict.winner;
}

function describeOutcome(verdict: EvalsVerdict): string {
  switch (displayedOutcome(verdict)) {
    case "baseline":
      return "Baseline won";
    case "candidate":
      return "Candidate won";
    case "tie":
      return verdict.order_agreement ? "Tie" : "Tie (order disagreement)";
    case "error":
      return "Judge error";
  }
}
