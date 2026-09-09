// Agent Setup module shell: opens on the Skills inventory — what is installed, where each file
// lives and how it is built — with the raw config-file browser one tab over.
import { useState } from "react";
import { AgentFilesTab } from "./components/AgentFilesTab";
import { SkillsTab } from "./skills/SkillsTab";
import "./AgentSetupModule.css";

type SetupTab = "skills" | "files";

const TABS: Array<{ key: SetupTab; label: string }> = [
  { key: "skills", label: "Skills" },
  { key: "files", label: "Config files" },
];

export function AgentSetupModule() {
  const [tab, setTab] = useState<SetupTab>("skills");

  return (
    <div className="agent-setup">
      <div
        className="segmented-control agent-setup__tabs"
        role="tablist"
        aria-label="Agent setup view"
      >
        {TABS.map((entry) => (
          <button
            key={entry.key}
            type="button"
            role="tab"
            aria-selected={tab === entry.key}
            className={`select-none${tab === entry.key ? " is-active" : ""}`}
            onClick={() => setTab(entry.key)}
          >
            {entry.label}
          </button>
        ))}
      </div>
      {tab === "skills" ? <SkillsTab /> : <AgentFilesTab />}
    </div>
  );
}
