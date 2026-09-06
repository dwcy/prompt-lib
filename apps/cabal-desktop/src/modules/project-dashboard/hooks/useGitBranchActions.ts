// Wires the Git health card's per-branch switch/delete buttons to the action-safety protocol,
// invalidating the git dashboard section for the current project on success.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { queryKeys } from "@/api/queryKeys";
import { useAction } from "@/hooks/useAction";
import { useProjectContextStore } from "@/stores/projectContext";

export function useGitBranchActions() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  const queryClient = useQueryClient();
  const switchAction = useAction("git.switch_branch");
  const deleteAction = useAction("git.delete_branch");

  useEffect(() => {
    if (switchAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({
      queryKey: queryKeys.scoped("dashboard", projectPath, "git"),
    });
    switchAction.reset();
  }, [switchAction.phase, switchAction.reset, queryClient, projectPath]);

  useEffect(() => {
    if (deleteAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({
      queryKey: queryKeys.scoped("dashboard", projectPath, "git"),
    });
    deleteAction.reset();
  }, [deleteAction.phase, deleteAction.reset, queryClient, projectPath]);

  return {
    switchAction,
    deleteAction,
    switchBranch: (branch: string) => switchAction.prepare({ branch }),
    deleteBranch: (branch: string) => deleteAction.prepare({ branch }),
  };
}
