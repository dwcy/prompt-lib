// The skill body as a collapsible heading outline: the shape of the instructions first, the
// wording second. Mount it with `key={skill.id}` so switching skills resets what is open.
import { useState } from "react";
import type { SkillBlock, SkillSection } from "@/api/agentSkills";
import { EmptyState } from "@/components/EmptyState";
import { SkillBlocks } from "./SkillBlocks";

export interface SkillOutlineProps {
  preamble: SkillBlock[];
  sections: SkillSection[];
}

export function SkillOutline({ preamble, sections }: SkillOutlineProps) {
  const [open, setOpen] = useState<Set<string>>(
    () => new Set(sections.length > 0 ? [sections[0].anchor] : []),
  );

  if (sections.length === 0 && preamble.length === 0) {
    return <EmptyState title="This file has no instructions in it" />;
  }

  const toggle = (anchor: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(anchor)) {
        next.delete(anchor);
      } else {
        next.add(anchor);
      }
      return next;
    });

  const allOpen = open.size === sections.length && sections.length > 0;

  return (
    <div className="skill-outline">
      {sections.length > 0 ? (
        <div className="skill-outline__controls">
          <span className="skill-outline__count select-none">
            {sections.length} section{sections.length === 1 ? "" : "s"}
          </span>
          <button
            type="button"
            className="skill-outline__toggle-all select-none"
            onClick={() =>
              setOpen(allOpen ? new Set() : new Set(sections.map((section) => section.anchor)))
            }
          >
            {allOpen ? "Collapse all" : "Expand all"}
          </button>
        </div>
      ) : null}

      {preamble.length > 0 ? (
        <div className="skill-outline__preamble">
          <SkillBlocks blocks={preamble} />
        </div>
      ) : null}

      <ul className="skill-outline__sections">
        {sections.map((section) => {
          const expanded = open.has(section.anchor);
          return (
            <li
              key={section.anchor}
              className="skill-outline__section"
              data-level={Math.min(section.level, 4)}
            >
              <button
                type="button"
                className="skill-outline__heading select-none"
                aria-expanded={expanded}
                onClick={() => toggle(section.anchor)}
              >
                <span className="skill-outline__caret" aria-hidden="true">
                  {expanded ? "▾" : "▸"}
                </span>
                <span className="skill-outline__title">{section.title}</span>
                <span className="skill-outline__level">H{section.level}</span>
              </button>
              {expanded ? (
                <div className="skill-outline__body">
                  <SkillBlocks blocks={section.blocks} />
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
