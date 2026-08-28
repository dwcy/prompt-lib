// Release news reference module: what shipped, where each feature lives in the UI, and how to use it.
import { useMemo, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ReleaseEntryCard } from "./ReleaseEntryCard";
import {
  RELEASE_SECTIONS,
  RELEASE_SUMMARY,
  RELEASE_TITLE,
  type ReleaseEntry,
  type ReleaseSection,
} from "./releaseNotes";
import "./ReleaseNotesModule.css";

function matches(entry: ReleaseEntry, needle: string): boolean {
  if (needle === "") return true;
  const haystack = [entry.title, entry.location, entry.purpose, ...entry.steps, entry.note ?? ""]
    .join(" ")
    .toLowerCase();
  return haystack.includes(needle);
}

function filterSections(needle: string): ReleaseSection[] {
  if (needle === "") return RELEASE_SECTIONS;
  return RELEASE_SECTIONS.map((section) => ({
    ...section,
    entries: section.entries.filter((entry) => matches(entry, needle)),
  })).filter((section) => section.entries.length > 0);
}

export function ReleaseNotesModule() {
  const [query, setQuery] = useState("");
  const [activeSection, setActiveSection] = useState<string | null>(null);

  const needle = query.trim().toLowerCase();
  const sections = useMemo(() => filterSections(needle), [needle]);
  const entryCount = useMemo(
    () => RELEASE_SECTIONS.reduce((total, section) => total + section.entries.length, 0),
    [],
  );
  const matchCount = sections.reduce((total, section) => total + section.entries.length, 0);
  const visible =
    activeSection === null ? sections : sections.filter((section) => section.id === activeSection);

  return (
    <div className="release-notes">
      <header className="release-notes__intro">
        <div>
          <span className="release-notes__eyebrow">Release news</span>
          <h2 className="release-notes__title">{RELEASE_TITLE}</h2>
          <p className="release-notes__summary">{RELEASE_SUMMARY}</p>
        </div>
        <label className="release-notes__search">
          <span className="release-notes__sr-only">Search release news</span>
          <input
            type="search"
            value={query}
            placeholder={`Search ${entryCount} features…`}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </header>

      <nav className="release-notes__filters" aria-label="Release sections">
        <button
          type="button"
          className={activeSection === null ? "is-active" : undefined}
          onClick={() => setActiveSection(null)}
        >
          All
        </button>
        {RELEASE_SECTIONS.map((section) => (
          <button
            key={section.id}
            type="button"
            className={activeSection === section.id ? "is-active" : undefined}
            onClick={() => setActiveSection(section.id)}
          >
            {section.title}
          </button>
        ))}
      </nav>

      {matchCount === 0 ? (
        <EmptyState
          title="Nothing matches that search"
          body="Try a screen name, a sidebar group, or a word from what you are trying to do."
        />
      ) : (
        visible.map((section) => (
          <section key={section.id} className="release-notes__section">
            <header className="release-notes__section-header">
              <h3>{section.title}</h3>
              <p>{section.blurb}</p>
            </header>
            <ul className="release-notes__list">
              {section.entries.map((entry) => (
                <ReleaseEntryCard key={entry.title} entry={entry} />
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
