// Minimal task+profile+repetition selector feeding CellDetail. The report/run-list contracts
// expose no cells-listing endpoint or repetition count, so repetition is a manual number input
// rather than a populated list — see the CellDetail contract gap noted in the module's report.
import { useState } from "react";

export interface CellPickerProps {
  task: string;
  onView: (profile: "baseline" | "candidate", repetition: number) => void;
}

export function CellPicker({ task, onView }: CellPickerProps) {
  const [profile, setProfile] = useState<"baseline" | "candidate">("baseline");
  const [repetition, setRepetition] = useState(1);

  return (
    <fieldset className="cell-picker">
      <legend className="select-none">View a cell for {task}</legend>
      <label className="select-none">
        <input
          type="radio"
          name={`${task}-cell-profile`}
          checked={profile === "baseline"}
          onChange={() => setProfile("baseline")}
        />
        Baseline
      </label>
      <label className="select-none">
        <input
          type="radio"
          name={`${task}-cell-profile`}
          checked={profile === "candidate"}
          onChange={() => setProfile("candidate")}
        />
        Candidate
      </label>
      <label className="select-none">
        Repetition
        <input
          type="number"
          min={1}
          value={repetition}
          onChange={(event) => setRepetition(Math.max(1, Number(event.currentTarget.value) || 1))}
        />
      </label>
      <button type="button" className="select-none" onClick={() => onView(profile, repetition)}>
        View cell
      </button>
    </fieldset>
  );
}
