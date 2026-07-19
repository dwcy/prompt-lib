// Severity toggle group for the diagnostics history query (GET /api/diagnostics?severity=).
export type SeverityFilterValue = "all" | "info" | "warning" | "error";

export interface SeverityFilterProps {
  value: SeverityFilterValue;
  onChange: (value: SeverityFilterValue) => void;
}

const OPTIONS: SeverityFilterValue[] = ["all", "info", "warning", "error"];

export function SeverityFilter({ value, onChange }: SeverityFilterProps) {
  return (
    // biome-ignore lint/a11y/useSemanticElements: toggle-button toolbar; aria-pressed per button already conveys state
    <div
      className="diagnostics__severity-filter select-none"
      role="group"
      aria-label="Filter by severity"
    >
      {OPTIONS.map((option) => (
        <button
          key={option}
          type="button"
          className={`diagnostics__severity-option${
            option === value ? " diagnostics__severity-option--active" : ""
          }`}
          aria-pressed={option === value}
          onClick={() => onChange(option)}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
