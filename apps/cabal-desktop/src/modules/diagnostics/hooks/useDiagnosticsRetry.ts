// "Retry this source": invalidates every cached query for the module a diagnostic event affected.
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/api/queryKeys";
import { MODULE_TO_SCOPED_QUERY_MODULE } from "@/modules/diagnostics/diagnosticsRetryMap";
import type { ModuleKey } from "@/modules/registry";
import { useProjectContextStore } from "@/stores/projectContext";

export function useDiagnosticsRetry(): (module: string) => void {
  const queryClient = useQueryClient();
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);

  return function retrySource(module: string): void {
    const scopedModule = MODULE_TO_SCOPED_QUERY_MODULE[module as ModuleKey];
    const queryKey =
      scopedModule !== undefined
        ? queryKeys.scoped(scopedModule, projectPath)
        : queryKeys.global(module);
    void queryClient.invalidateQueries({ queryKey });
  };
}
