// Orchestrates the project.select prepare→confirm→execute flow for the gate/switcher UI: wraps
// useAction, then invalidates GET /api/project on success so useProjectContextSync (App.tsx) can
// promote the new context into the shared store, and auto-resets so the ConfirmDialog closes
// instead of sitting on an already-executed ticket.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { queryKeys } from "@/api/queryKeys";
import { useAction } from "@/hooks/useAction";

export function useProjectGate() {
  const action = useAction("project.select");
  const queryClient = useQueryClient();

  useEffect(() => {
    if (action.phase !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.project.current() });
    action.reset();
  }, [action.phase, action.reset, queryClient]);

  function selectPath(path: string): void {
    action.prepare({ path });
  }

  return { action, selectPath };
}
