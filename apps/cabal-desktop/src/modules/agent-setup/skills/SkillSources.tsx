// Every folder the inventory searched, with its absolute path and how many definitions it held —
// including the ones that do not exist, because "nothing here" is the answer to "why is my skill
// missing?". Also flags repo skills that were never deployed to the home config.
import { useState } from "react";
import type { SkillInventory } from "@/api/agentSkills";

export interface SkillSourcesProps {
  inventory: SkillInventory;
}

export function SkillSources({ inventory }: SkillSourcesProps) {
  const [open, setOpen] = useState(false);
  const unapplied = inventory.unapplied_repo_skills;

  return (
    <section className="skill-sources">
      <button
        type="button"
        className="skill-sources__toggle select-none"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span aria-hidden="true">{open ? "▾" : "▸"}</span>
        Folders searched
        <span className="skill-sources__count">{inventory.sources.length}</span>
      </button>
      {open ? (
        <div className="skill-sources__body">
          <ul className="skill-sources__list">
            {inventory.sources.map((source) => (
              <li key={source.key} data-missing={!source.exists}>
                <span className="skill-sources__label">
                  {source.label}
                  {source.plugin_version !== null ? ` v${source.plugin_version}` : ""}
                </span>
                <code className="skill-sources__path">{source.path}</code>
                <span className="skill-sources__value">
                  {source.exists ? `${source.count} found` : "does not exist"}
                </span>
              </li>
            ))}
          </ul>
          {unapplied.length > 0 ? (
            <p className="skill-sources__warning">
              {unapplied.length} skill{unapplied.length === 1 ? "" : "s"} in this repo
              {inventory.repo_skills_path !== null ? ` (${inventory.repo_skills_path})` : ""} never
              reached your home config: {unapplied.map((entry) => entry.name).join(", ")}. Deploy to
              make them loadable.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
