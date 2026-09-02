// Single recursive folder/file row in the Agent Setup tree: a directory toggles its own
// expand/collapse state; a file is a click target that reports its rel_path up to the parent.
import { useState } from "react";
import type { AgentConfigEntry } from "@/api/agentConfig";
import { formatBytes, formatModified } from "../agentSetupFormat";

export interface AgentConfigTreeNodeProps {
  entry: AgentConfigEntry;
  depth: number;
  selectedPath: string | null;
  onSelectFile: (relPath: string) => void;
}

export function AgentConfigTreeNode({
  entry,
  depth,
  selectedPath,
  onSelectFile,
}: AgentConfigTreeNodeProps) {
  const [expanded, setExpanded] = useState(depth < 1);
  const indent = { paddingLeft: `${depth}rem` };

  if (entry.kind === "file") {
    return (
      <li className="agent-config-tree__row" style={indent}>
        <button
          type="button"
          className={`agent-config-tree__file${entry.rel_path === selectedPath ? " is-selected" : ""}`}
          onClick={() => onSelectFile(entry.rel_path)}
        >
          <span className="agent-config-tree__name">{entry.name}</span>
          <span className="agent-config-tree__meta">
            {formatBytes(entry.size_bytes)} · {formatModified(entry.modified_at)}
          </span>
        </button>
      </li>
    );
  }

  const children = entry.children ?? [];
  return (
    <li className="agent-config-tree__row" style={indent}>
      <button
        type="button"
        className="agent-config-tree__dir"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
      >
        <span className="agent-config-tree__caret" aria-hidden="true">
          {expanded ? "▾" : "▸"}
        </span>
        <span className="agent-config-tree__name">{entry.name}</span>
        <span className="agent-config-tree__meta">{children.length} item(s)</span>
      </button>
      {expanded && children.length > 0 ? (
        <ul className="agent-config-tree__children">
          {children.map((child) => (
            <AgentConfigTreeNode
              key={child.rel_path}
              entry={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              onSelectFile={onSelectFile}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}
