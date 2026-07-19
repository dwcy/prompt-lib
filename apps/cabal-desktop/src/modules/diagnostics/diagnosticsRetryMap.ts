// Maps a DiagnosticEvent.module (a registry ModuleKey) to the query-key module name its own hooks
// key their TanStack Query cache under (api/queryKeys.ts's PROJECT_SCOPED_MODULES) — lets "retry
// this source" invalidate the exact cache prefix that module's hooks actually use, without
// diagnostics needing bespoke per-module retry logic. Modules with no dedicated hooks yet fall back
// to the generic global(module) key in useDiagnosticsRetry.ts, which is a harmless no-op today and
// becomes meaningful automatically as later phases land their own query hooks.
import type { ProjectScopedModule } from "@/api/queryKeys";
import type { ModuleKey } from "@/modules/registry";

export const MODULE_TO_SCOPED_QUERY_MODULE: Partial<Record<ModuleKey, ProjectScopedModule>> = {
  project_dashboard: "dashboard",
  sessions: "sessionsPanel",
  local_config: "localConfig",
  settings: "settings",
  package_security: "security",
  init_wizard: "init",
  home_overview: "homeOverview",
};
