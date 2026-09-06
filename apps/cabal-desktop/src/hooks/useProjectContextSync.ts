// Keeps the Zustand project-context store in sync with GET /api/project so its subscribe-based
// cache invalidation (stores/projectContext.ts) actually fires on every project switch (T036).
// Gate rule: `selected` stays null until the backend reports a real `selected_at` — i.e. the
// project has been explicitly chosen at least once — so first launch shows the project gate even
// though the backend already resolved some fallback cwd as the current ProjectContext.
import { useEffect } from "react";
import { useProjectContext } from "@/api/project";
import { useProjectContextStore } from "@/stores/projectContext";

export function useProjectContextSync(): ReturnType<typeof useProjectContext> {
  const query = useProjectContext();
  const setProject = useProjectContextStore((state) => state.setProject);
  const setRecents = useProjectContextStore((state) => state.setRecents);

  useEffect(() => {
    if (query.data === undefined) return;
    setRecents(query.data.recents.map((recent) => ({ path: recent.path, name: recent.name })));
    if (query.data.selected_at === null) return;
    setProject({ path: query.data.path, name: query.data.name });
  }, [query.data, setProject, setRecents]);

  return query;
}
