// Root list for the Agent Setup folder browser: renders each top-level entry as a recursive
// AgentConfigTreeNode and surfaces a notice when the backend capped the walk.
import type { AgentConfigEntry } from "@/api/agentConfig";
import { EmptyState } from "@/components/EmptyState";
import { AgentConfigTreeNode } from "./AgentConfigTreeNode";

export interface AgentConfigTreeProps {
  roots: AgentConfigEntry[];
  truncated: boolean;
  selectedPath: string | null;
  onSelectFile: (relPath: string) => void;
}

export function AgentConfigTree({
  roots,
  truncated,
  selectedPath,
  onSelectFile,
}: AgentConfigTreeProps) {
  if (roots.length === 0) {
    return (
      <div className="agent-config-tree">
        <EmptyState title="This folder is empty" />
      </div>
    );
  }
  return (
    <div className="agent-config-tree">
      <ul className="agent-config-tree__root">
        {roots.map((entry) => (
          <AgentConfigTreeNode
            key={entry.rel_path}
            entry={entry}
            depth={0}
            selectedPath={selectedPath}
            onSelectFile={onSelectFile}
          />
        ))}
      </ul>
      {truncated ? (
        <p className="agent-config-tree__truncated">
          Showing a capped subset — this folder has more entries than fit in one listing.
        </p>
      ) : null}
    </div>
  );
}
