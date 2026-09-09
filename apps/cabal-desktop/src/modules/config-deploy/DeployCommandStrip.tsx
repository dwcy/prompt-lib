// The deploy queue: what is selected, how far through review → queue → write you are, and the
// three buttons that move it along. Selection state lives in the panel; this only reports it.
export interface DeployCommandStripProps {
  selectedPaths: string[];
  driftCount: number;
  diffReviewed: boolean;
  selectableCount: number;
  onSelectDrift: () => void;
  onClear: () => void;
  onApply: () => void;
}

const PREVIEW_PATHS = 3;

function stepClass(done: boolean): string {
  return done ? "cfg-deploy__step cfg-deploy__step--done" : "cfg-deploy__step";
}

export function DeployCommandStrip({
  selectedPaths,
  driftCount,
  diffReviewed,
  selectableCount,
  onSelectDrift,
  onClear,
  onApply,
}: DeployCommandStripProps) {
  const selectedCount = selectedPaths.length;
  const summary =
    selectedCount === 0
      ? `${driftCount} drifted file(s) are available for review.`
      : selectedPaths.slice(0, PREVIEW_PATHS).join(", ");

  return (
    <section className="cfg-deploy__command-strip">
      <div className="cfg-deploy__command-summary">
        <span className="cfg-deploy__eyebrow">Deploy queue</span>
        <strong>
          {selectedCount === 0 ? "Nothing selected" : `${selectedCount} file(s) ready`}
        </strong>
        <p>{summary}</p>
      </div>
      <ol className="cfg-deploy__steps" aria-label="Deploy workflow">
        <li className={stepClass(diffReviewed)}>Review diff</li>
        <li className={stepClass(selectedCount > 0)}>Build queue</li>
        <li className="cfg-deploy__step">Confirm write</li>
      </ol>
      <div className="cfg-deploy__toolbar">
        <button
          type="button"
          className="cfg-deploy__toolbar-btn"
          onClick={onSelectDrift}
          disabled={selectableCount === 0}
        >
          Select drift
        </button>
        <button
          type="button"
          className="cfg-deploy__toolbar-btn"
          onClick={onClear}
          disabled={selectedCount === 0}
        >
          Clear
        </button>
        <button
          type="button"
          className="cfg-deploy__toolbar-btn cfg-deploy__toolbar-btn--primary"
          onClick={onApply}
          disabled={selectedCount === 0}
        >
          Apply {selectedCount}
        </button>
      </div>
    </section>
  );
}
