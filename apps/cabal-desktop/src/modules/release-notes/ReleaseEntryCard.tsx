// One release-note entry: what it is, where to find it in the sidebar, and the steps to use it.
import type { ReleaseEntry } from "./releaseNotes";

export interface ReleaseEntryCardProps {
  entry: ReleaseEntry;
}

export function ReleaseEntryCard({ entry }: ReleaseEntryCardProps) {
  return (
    <li className="release-entry">
      <header className="release-entry__header">
        <h4>{entry.title}</h4>
        <span className="release-entry__location">{entry.location}</span>
      </header>
      <p className="release-entry__purpose">{entry.purpose}</p>
      <ol className="release-entry__steps">
        {entry.steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      {entry.note ? <p className="release-entry__note">{entry.note}</p> : null}
    </li>
  );
}
