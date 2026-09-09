// One labelled absolute path with a copy button. Used both in the detail header (the file you
// would open) and in the Where tab (folder, repo source).
import { useState } from "react";

export interface SkillPathRowProps {
  label: string;
  path: string;
}

export function SkillPathRow({ label, path }: SkillPathRowProps) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="skill-where__row">
      <span className="skill-where__label select-none">{label}</span>
      <code className="skill-where__path">{path}</code>
      <button
        type="button"
        className="skill-where__copy select-none"
        onClick={() => {
          void navigator.clipboard.writeText(path).then(() => setCopied(true));
        }}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
