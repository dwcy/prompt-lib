// Install/update action panel for the Tools detail drawer: gates by ToolStatus.state, drives the
// prepare -> ConfirmDialog -> execute -> JobPane chain, and invalidates the tool's status/catalog/
// detail queries once the resulting job reaches a terminal state (T043).
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useJob } from "@/api/jobs";
import { queryKeys } from "@/api/queryKeys";
import type { ToolDetail, ToolStatusState } from "@/api/tools";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { JobPane } from "@/components/JobPane";
import { useAction } from "@/hooks/useAction";
import { toolActionForState } from "@/modules/tools/toolActionGating";

const TERMINAL_JOB_STATES = new Set(["succeeded", "failed", "cancelled"]);

export interface ToolActionPanelProps {
  tool: ToolDetail;
}

export function ToolActionPanel({ tool }: ToolActionPanelProps) {
  const actionKind = toolActionForState(tool.status.state);
  const action = useAction(actionKind ?? "tools.install");
  const [selectedVersion, setSelectedVersion] = useState(
    tool.status.latest_version ?? tool.versions_available[0] ?? "",
  );
  useInvalidateToolOnJobTerminal(action.jobId, tool.key);

  if (actionKind === null) {
    return (
      <p className="tool-action-panel__unavailable" role="status">
        {unavailableReason(tool.status.state)}
      </p>
    );
  }

  const actionLabel = actionKind === "tools.install" ? "Install" : "Update";

  return (
    <div className="tool-action-panel">
      {tool.versions_available.length > 0 ? (
        <label className="tool-action-panel__version select-none" htmlFor="tool-action-version">
          Version
          <select
            id="tool-action-version"
            value={selectedVersion}
            onChange={(event) => setSelectedVersion(event.target.value)}
          >
            {tool.versions_available.map((version) => (
              <option key={version} value={version}>
                {version}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <button
        type="button"
        onClick={() =>
          action.prepare(
            selectedVersion.length > 0
              ? { key: tool.key, version: selectedVersion }
              : { key: tool.key },
          )
        }
      >
        {actionLabel}
      </button>

      <ConfirmDialog action={action} actionTitle={`${actionLabel} ${tool.label}`} />

      {action.jobId !== null ? <JobPane jobId={action.jobId} /> : null}
    </div>
  );
}

function unavailableReason(state: ToolStatusState): string {
  if (state === "manual_required") return "This tool requires manual installation.";
  if (state === "unsupported") return "This tool is not supported on your platform.";
  return "No install or update action is available for this tool right now.";
}

// Polls the job (sharing JobPane's own query cache entry) until it reaches a terminal state, then
// invalidates the tool's status/catalog/detail queries exactly once so the table/drawer refresh.
function useInvalidateToolOnJobTerminal(jobId: string | null, toolKey: string): void {
  const queryClient = useQueryClient();
  const jobQuery = useJob(jobId ?? "none", {
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state !== undefined && TERMINAL_JOB_STATES.has(state) ? false : 1_500;
    },
  });
  const invalidatedJobId = useRef<string | null>(null);

  useEffect(() => {
    const state = jobQuery.data?.state;
    if (jobId === null || state === undefined || !TERMINAL_JOB_STATES.has(state)) return;
    if (invalidatedJobId.current === jobId) return;
    invalidatedJobId.current = jobId;
    queryClient.invalidateQueries({ queryKey: queryKeys.global("tools", "status") });
    queryClient.invalidateQueries({ queryKey: queryKeys.global("tools", "catalog") });
    queryClient.invalidateQueries({ queryKey: queryKeys.global("tools", "detail", toolKey) });
  }, [jobQuery.data?.state, jobId, toolKey, queryClient]);
}
