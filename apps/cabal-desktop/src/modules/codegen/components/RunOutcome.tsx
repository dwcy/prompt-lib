// T026: renders the four persisted codegen run outcomes distinctly, plus the no-run-record case
// where the process failed outright before any run record was ever written (data-model A3). Do
// not add a fifth outcome from CLI exit codes — halted_at_ceiling vs aborted_environment IS the
// environment-vs-defect distinction FR-017 requires.
import type { CodegenRetryBudget, CodegenRunOutcome } from "@/api/codegen";
import { StatePill, type StatePillVariant } from "@/components/StatePill";

export interface RunOutcomeProps {
  /** null: the process ended before any run record was written (EXIT_FAILURE / EXIT_USAGE). */
  outcome: CodegenRunOutcome | null;
  retryBudget?: CodegenRetryBudget;
  detail?: string | null;
}

const OUTCOME_COPY: Record<
  CodegenRunOutcome,
  { label: string; variant: StatePillVariant; description: string }
> = {
  completed: {
    label: "Completed",
    variant: "succeeded",
    description: "The generated code was written and verified.",
  },
  rejected_at_gate: {
    label: "Rejected at gate",
    variant: "rejected",
    description: "Declined at the approval gate — a decision, not a failure. Nothing was written.",
  },
  halted_at_ceiling: {
    label: "Halted at retry ceiling",
    variant: "halted",
    description: "Repair attempts were exhausted before the code defect was resolved.",
  },
  aborted_environment: {
    label: "Blocked by environment problem",
    variant: "environment",
    description: "The toolchain itself failed, not the generated code. No retry budget was spent.",
  },
};

export function RunOutcome({ outcome, retryBudget, detail }: RunOutcomeProps) {
  if (outcome === null) {
    return (
      <div className="run-outcome run-outcome--no-record">
        <StatePill variant="unknown" label="No run record" />
        <p className="run-outcome__description">
          {detail ??
            "The process ended before any run record was written — this is not one of the four tracked outcomes."}
        </p>
      </div>
    );
  }

  const copy = OUTCOME_COPY[outcome];
  const showRetryBudget = outcome === "halted_at_ceiling" && retryBudget !== undefined;

  return (
    <div className={`run-outcome run-outcome--${outcome}`}>
      <StatePill variant={copy.variant} label={copy.label} />
      <p className="run-outcome__description">{copy.description}</p>
      {showRetryBudget && retryBudget !== undefined ? (
        <p className="run-outcome__retry-budget">
          {retryBudget.consumed} of {retryBudget.ceiling} repair attempts used
        </p>
      ) : null}
    </div>
  );
}
