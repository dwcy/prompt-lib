// Hierarchical TanStack Query keys: global module keys plus project-scoped keys keyed on project path.
const ROOT = "cabal" as const;

export const PROJECT_SCOPED_MODULES = [
  "dashboard",
  "sessionsPanel",
  "localConfig",
  "settings",
  "security",
  "init",
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
  // Global modules (Tools, MCP user scope, Config Deployment, Knowledge, Services, Environment)
  // ignore project context; each future module keys its own queries under its own name.
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
