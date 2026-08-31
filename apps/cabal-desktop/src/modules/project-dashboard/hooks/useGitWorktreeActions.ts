// Wires the Git health card's per-worktree switch/remove buttons: switching reuses the existing
// project.select action (a worktree is just another directory to make the active project);
// removing goes through the new git.remove_worktree action.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { queryKeys } from "@/api/queryKeys";
import { useAction } from "@/hooks/useAction";
import { useProjectGate } from "@/modules/project-gate/hooks/useProjectGate";
import { useProjectContextStore } from "@/stores/projectContext";

export function useGitWorktreeActions() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  const queryClient = useQueryClient();
  const { action: switchAction, selectPath } = useProjectGate();
  const removeAction = useAction("git.remove_worktree");

  useEffect(() => {
    if (removeAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({
      queryKey: queryKeys.scoped("dashboard", projectPath, "git"),
    });
    removeAction.reset();
  }, [removeAction.phase, removeAction.reset, queryClient, projectPath]);

  return {
    switchAction,
    removeAction,
    activeProjectPath: projectPath,
    switchWorktree: selectPath,
    removeWorktree: (path: string) => removeAction.prepare({ path }),
  };
}
