// Zustand store for the active project; switching it invalidates every project-scoped query key.
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { queryClient } from "@/api/queryClient";
import { projectScopedKeyPrefixes } from "@/api/queryKeys";

export interface ProjectSummary {
  path: string;
  name: string;
}

interface ProjectContextState {
  selected: ProjectSummary | null;
  recents: ProjectSummary[];
}

interface ProjectContextActions {
  setProject: (project: ProjectSummary) => void;
  clearProject: () => void;
  setRecents: (recents: ProjectSummary[]) => void;
}

export const useProjectContextStore = create<ProjectContextState & ProjectContextActions>()(
  persist(
    (set) => ({
      selected: null,
      recents: [],
      setProject: (project) => set({ selected: project }),
      clearProject: () => set({ selected: null }),
      setRecents: (recents) => set({ recents }),
    }),
    { name: "cabal.projectContext" },
  ),
);

useProjectContextStore.subscribe((state, previousState) => {
  const nextPath = state.selected?.path ?? null;
  const previousPath = previousState.selected?.path ?? null;
  if (nextPath === previousPath) return;
  for (const key of projectScopedKeyPrefixes(nextPath)) {
    void queryClient.invalidateQueries({ queryKey: key });
  }
});
