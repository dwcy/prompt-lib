// Hierarchical TanStack Query keys: global module keys plus project-scoped keys keyed on project path.
const ROOT = "cabal" as const;

export const PROJECT_SCOPED_MODULES = [
  "dashboard",
  "sessionsPanel",
  "localConfig",
  "settings",
  "security",
  "init",
  // Home Overview aggregates dashboard_summary/recent_sessions for the CURRENT project (data-model.md
  // doesn't list it explicitly under either the scoped or global relationship bullet, but its payload
  // changes when the project switches, same as project_dashboard) — scoped so project.select
  // invalidates it too (T036). Diagnostics stays global: DiagnosticEvent is keyed by module, not project.
  "homeOverview",
  // README + docs/ come from the current project's working tree, so switching projects must
  // invalidate them the same way project_dashboard does.
  "docs",
  // Both target the currently selected project (spec Assumptions, FR-010): the codegen module
  // generates against it, and the eval module reads its evals/ tree — switching projects must
  // invalidate both (021-codegen-eval-modules).
  "codegen",
  "evals",
] as const;

export type ProjectScopedModule = (typeof PROJECT_SCOPED_MODULES)[number];

export const queryKeys = {
  health: () => [ROOT, "health"] as const,
  diagnostics: (params: { limit?: number; severity?: string } = {}) =>
    [ROOT, "diagnostics", params] as const,
  jobs: {
    all: () => [ROOT, "jobs"] as const,
    detail: (jobId: string) => [ROOT, "jobs", jobId] as const,
  },
  project: {
    current: () => [ROOT, "project"] as const,
    recents: () => [ROOT, "project", "recents"] as const,
  },
  // Global modules (Tools, MCP user scope, Config Deployment, Knowledge, Services, Environment,
  // Diagnostics) ignore project context; each module keys its own queries under its own name.
  global: (module: string, ...segments: Array<string | number>) =>
    [ROOT, "global", module, ...segments] as const,
  scoped: (
    module: ProjectScopedModule,
    projectPath: string | null,
    ...segments: Array<string | number>
  ) => [ROOT, "scoped", module, projectPath ?? "no-project", ...segments] as const,
};

export function projectScopedKeyPrefixes(projectPath: string | null) {
  return PROJECT_SCOPED_MODULES.map((module) => queryKeys.scoped(module, projectPath));
}
