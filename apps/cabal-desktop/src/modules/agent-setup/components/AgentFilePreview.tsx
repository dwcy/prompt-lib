// Read-only content preview for the file currently selected in the Agent Setup tree.
import type { ReactNode } from "react";
import { type AgentConfigScope, type AgentKey, useAgentConfigFile } from "@/api/agentConfig";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { formatBytes } from "../agentSetupFormat";

export interface AgentFilePreviewProps {
  agent: AgentKey;
  scope: AgentConfigScope;
  relPath: string | null;
}

export function AgentFilePreview({ agent, scope, relPath }: AgentFilePreviewProps) {
  const fileQuery = useAgentConfigFile(agent, scope, relPath);

  let body: ReactNode;
  if (relPath === null) {
    body = <EmptyState title="Select a file to preview its contents" />;
  } else if (fileQuery.isPending) {
    body = <EmptyState title="Loading file…" />;
  } else if (fileQuery.isError) {
    body = <EmptyState title="Could not load file" body={fileQuery.error.message} />;
  } else if (fileQuery.data.binary) {
    body = <EmptyState title="Binary file" body="This file cannot be previewed as text." />;
  } else {
    body = (
      <>
        <pre className="agent-file-preview__content">{fileQuery.data.content}</pre>
        {fileQuery.data.truncated ? (
          <p className="agent-file-preview__truncated">
            Preview truncated at {formatBytes(fileQuery.data.size_bytes)}.
          </p>
        ) : null}
      </>
    );
  }

  return (
    <section className="agent-file-preview" aria-label="File preview">
      <header className="agent-file-preview__header">
        <strong>{relPath ?? "No file selected"}</strong>
        {fileQuery.data ? <span>{formatBytes(fileQuery.data.size_bytes)}</span> : null}
        {relPath !== null ? (
          <RefreshButton
            label="file preview"
            onRefresh={() => void fileQuery.refetch()}
            isFetching={fileQuery.isFetching}
          />
        ) : null}
      </header>
      {body}
    </section>
  );
}
