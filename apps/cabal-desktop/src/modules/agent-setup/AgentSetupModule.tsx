// Agent Setup module: browses the real global and per-project local config folders for
// Claude, Codex, and Antigravity — an agent tab row plus a Global/Local scope switch per agent.
import type { ReactNode } from "react";
import { useState } from "react";
import { type AgentConfigScope, type AgentKey, useAgentConfigTree } from "@/api/agentConfig";
import { ApiError } from "@/api/errors";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import { useProjectContextStore } from "@/stores/projectContext";
import { AgentConfigTree } from "./components/AgentConfigTree";
import { AgentFilePreview } from "./components/AgentFilePreview";
import "./AgentSetupModule.css";

const AGENT_TABS: Array<{ key: AgentKey; label: string }> = [
  { key: "claude", label: "Claude" },
  { key: "codex", label: "Codex" },
  { key: "antigravity", label: "Antigravity" },
];

function ChooseProjectPrompt({ onChoose }: { onChoose: () => void }) {
  return (
    <EmptyState
      title="Select a project first"
      body="Local agent config is read from the currently selected project."
      action={
        <button type="button" onClick={onChoose}>
          Choose a project
        </button>
      }
    />
  );
}

export function AgentSetupModule() {
  const [agent, setAgent] = useState<AgentKey>("claude");
  const [scope, setScope] = useState<AgentConfigScope>("global");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const projectSelected = useProjectContextStore((state) => state.selected !== null);
  const { navigateToModule } = useModuleNavigation();
  const treeQuery = useAgentConfigTree(agent, scope);
  const chooseProject = () => navigateToModule("project_gate");

  function selectAgent(next: AgentKey) {
    setAgent(next);
    setSelectedPath(null);
  }

  function selectScope(next: AgentConfigScope) {
    setScope(next);
    setSelectedPath(null);
  }

  let body: ReactNode;
  if (scope === "local" && !projectSelected) {
    body = <ChooseProjectPrompt onChoose={chooseProject} />;
  } else if (treeQuery.isPending) {
    body = <EmptyState title="Reading folder structure…" />;
  } else if (treeQuery.isError) {
    const noProject =
      treeQuery.error instanceof ApiError && treeQuery.error.code === "no_project_selected";
    body = noProject ? (
      <ChooseProjectPrompt onChoose={chooseProject} />
    ) : (
      <EmptyState title="Could not load the folder structure" body={treeQuery.error.message} />
    );
  } else if (!treeQuery.data.exists) {
    body = (
      <EmptyState
        title="Nothing here yet"
        body={`${treeQuery.data.base_path} does not exist on this machine.`}
      />
    );
  } else {
    body = (
      <div className="agent-setup__body">
        <AgentConfigTree
          roots={treeQuery.data.roots}
          truncated={treeQuery.data.truncated}
          selectedPath={selectedPath}
          onSelectFile={setSelectedPath}
        />
        <AgentFilePreview agent={agent} scope={scope} relPath={selectedPath} />
      </div>
    );
  }

  return (
    <div className="agent-setup">
      <div className="segmented-control agent-setup__agent-tabs" role="tablist" aria-label="Agent">
        {AGENT_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={agent === tab.key}
            className={`select-none${agent === tab.key ? " is-active" : ""}`}
            onClick={() => selectAgent(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <section className="agent-setup__panel">
        <header className="agent-setup__panel-header">
          <div className="segmented-control" role="tablist" aria-label="Config scope">
            <button
              type="button"
              role="tab"
              aria-selected={scope === "global"}
              className={`select-none${scope === "global" ? " is-active" : ""}`}
              onClick={() => selectScope("global")}
            >
              Global
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={scope === "local"}
              className={`select-none${scope === "local" ? " is-active" : ""}`}
              onClick={() => selectScope("local")}
            >
              Local
            </button>
          </div>
          {treeQuery.data ? (
            <code className="agent-setup__base-path">{treeQuery.data.base_path}</code>
          ) : null}
          <RefreshButton
            label={`${agent} ${scope} config`}
            onRefresh={() => void treeQuery.refetch()}
            isFetching={treeQuery.isFetching}
          />
        </header>
        {body}
      </section>
    </div>
  );
}
