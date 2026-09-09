// The files a skill folder ships next to SKILL.md — references/, scripts/, assets/ — with an
// on-demand text preview of the one you pick. These are what the skill pulls in while it runs.
import { useState } from "react";
import { type SkillBundledFile, useSkillAsset } from "@/api/agentSkills";
import { EmptyState } from "@/components/EmptyState";
import { formatBytes } from "./skillPresentation";

export interface SkillBundlesProps {
  skillId: string;
  files: SkillBundledFile[];
}

function groupFiles(
  files: SkillBundledFile[],
): Array<{ group: string; files: SkillBundledFile[] }> {
  const groups = new Map<string, SkillBundledFile[]>();
  for (const file of files) {
    const key = file.group === "" ? "In the skill folder" : file.group;
    const existing = groups.get(key);
    if (existing === undefined) {
      groups.set(key, [file]);
    } else {
      existing.push(file);
    }
  }
  return [...groups.entries()].map(([group, entries]) => ({ group, files: entries }));
}

export function SkillBundles({ skillId, files }: SkillBundlesProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const assetQuery = useSkillAsset(skillId, selected);

  if (files.length === 0) {
    return (
      <EmptyState
        title="Nothing bundled"
        body="This skill is a single SKILL.md — it loads no extra reference files or scripts."
      />
    );
  }

  return (
    <div className="skill-bundles">
      <div className="skill-bundles__list">
        {groupFiles(files).map((entry) => (
          <div key={entry.group} className="skill-bundles__group">
            <h4 className="skill-bundles__group-title select-none">{entry.group}</h4>
            <ul>
              {entry.files.map((file) => (
                <li key={file.rel_path}>
                  <button
                    type="button"
                    className={`skill-bundles__file select-none${file.rel_path === selected ? " is-selected" : ""}`}
                    disabled={!file.previewable}
                    title={file.previewable ? file.rel_path : "Not a text file — no preview"}
                    onClick={() => setSelected(file.rel_path)}
                  >
                    <span className="skill-bundles__file-name">{file.name}</span>
                    <span className="skill-bundles__file-meta">{formatBytes(file.size_bytes)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="skill-bundles__preview">
        {selected === null ? (
          <EmptyState title="Pick a file to read it" />
        ) : assetQuery.isPending ? (
          <EmptyState title="Loading file" animated />
        ) : assetQuery.isError ? (
          <EmptyState title="Could not read that file" body={assetQuery.error.message} />
        ) : assetQuery.data.binary ? (
          <EmptyState title="Binary file" body="This file cannot be shown as text." />
        ) : (
          <pre className="skill-bundles__content">{assetQuery.data.content}</pre>
        )}
      </div>
    </div>
  );
}
