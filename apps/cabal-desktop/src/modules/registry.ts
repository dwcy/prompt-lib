// Static registry of every nav module: nav grouping, title, delivery phase, and page component
// (or null pre-launch, routed to the shared ModuleUnavailable placeholder).
import { type ComponentType, type LazyExoticComponent, lazy } from "react";
import { ProjectGateModule } from "@/modules/project-gate/ProjectGateModule";

const AccountModule = lazy(() =>
  import("@/modules/account/AccountModule").then((module) => ({ default: module.AccountModule })),
);
const DocsModule = lazy(() =>
  import("@/modules/docs/DocsModule").then((module) => ({ default: module.DocsModule })),
);
const CleanupRestoreModule = lazy(() =>
  import("@/modules/cleanup-restore/CleanupRestoreModule").then((module) => ({
    default: module.CleanupRestoreModule,
  })),
);
const CodexModule = lazy(() =>
  import("@/modules/codex/CodexModule").then((module) => ({ default: module.CodexModule })),
);
const ConfigDeployModule = lazy(() =>
  import("@/modules/config-deploy/ConfigDeployModule").then((module) => ({
    default: module.ConfigDeployModule,
  })),
);
const DiagnosticsModule = lazy(() =>
  import("@/modules/diagnostics/DiagnosticsModule").then((module) => ({
    default: module.DiagnosticsModule,
  })),
);
const DoctorModule = lazy(() =>
  import("@/modules/doctor/DoctorModule").then((module) => ({ default: module.DoctorModule })),
);
const EnvironmentModule = lazy(() =>
  import("@/modules/environment/EnvironmentModule").then((module) => ({
    default: module.EnvironmentModule,
  })),
);
const GitIdentityModule = lazy(() =>
  import("@/modules/git-identity/GitIdentityModule").then((module) => ({
    default: module.GitIdentityModule,
  })),
);
const InitProjectModule = lazy(() =>
  import("@/modules/init-project/InitProjectModule").then((module) => ({
    default: module.InitProjectModule,
  })),
);
const KnowledgeModule = lazy(() =>
  import("@/modules/knowledge/KnowledgeModule").then((module) => ({
    default: module.KnowledgeModule,
  })),
);
const LocalConfigModule = lazy(() =>
  import("@/modules/local-config/LocalConfigModule").then((module) => ({
    default: module.LocalConfigModule,
  })),
);
const McpModule = lazy(() =>
  import("@/modules/mcp/McpModule").then((module) => ({ default: module.McpModule })),
);
const ModelAssignmentsModule = lazy(() =>
  import("@/modules/model-assignments/ModelAssignmentsModule").then((module) => ({
    default: module.ModelAssignmentsModule,
  })),
);
const OverviewModule = lazy(() =>
  import("@/modules/overview/OverviewModule").then((module) => ({
    default: module.OverviewModule,
  })),
);
const PackageSecurityModule = lazy(() =>
  import("@/modules/package-security/PackageSecurityModule").then((module) => ({
    default: module.PackageSecurityModule,
  })),
);
const ProjectDashboardModule = lazy(() =>
  import("@/modules/project-dashboard/ProjectDashboardModule").then((module) => ({
    default: module.ProjectDashboardModule,
  })),
);
const ProviderModule = lazy(() =>
  import("@/modules/provider/ProviderModule").then((module) => ({
    default: module.ProviderModule,
  })),
);
const ServicesModule = lazy(() =>
  import("@/modules/services/ServicesModule").then((module) => ({
    default: module.ServicesModule,
  })),
);
const SessionsModule = lazy(() =>
  import("@/modules/sessions/SessionsModule").then((module) => ({
    default: module.SessionsModule,
  })),
);
const ReleaseNotesModule = lazy(() =>
  import("@/modules/release-notes/ReleaseNotesModule").then((module) => ({
    default: module.ReleaseNotesModule,
  })),
);
const ScheduledTasksModule = lazy(() =>
  import("@/modules/scheduled-tasks/ScheduledTasksModule").then((module) => ({
    default: module.ScheduledTasksModule,
  })),
);
const SettingsModule = lazy(() =>
  import("@/modules/settings/SettingsModule").then((module) => ({
    default: module.SettingsModule,
  })),
);
const ToolsModule = lazy(() =>
  import("@/modules/tools/ToolsModule").then((module) => ({ default: module.ToolsModule })),
);

export type ModuleGroup = "machine" | "repo" | "infrastructure" | "agents" | "reference";

export const MODULE_GROUP_LABELS: Record<ModuleGroup, string> = {
  machine: "Machine",
  repo: "Repo",
  infrastructure: "Infrastructure",
  agents: "Agents",
  reference: "Reference",
};

export const MODULE_NAV_LABELS: Record<ModuleKey, string> = {
  codegen: ".NET Codegen",
  evals: "Agent Evals",
  project_gate: "Switch project",
  home_overview: "Overview",
  project_dashboard: "Project health",
  tools: "Tools",
  config_deploy: "Deploy config",
  cleanup_restore: "Recovery",
  settings: "Settings",
  mcp: "MCP connectors",
  local_config: "Project setup",
  knowledge: "Knowledge",
  services: "Services",
  package_security: "Package security",
  sessions: "Sessions & cost",
  scheduled_tasks: "Scheduled tasks",
  account: "Claude config",
  doctor: "Config doctor",
  model_assignments: "Model assignments",
  environment: "Environment",
  git_identity: "Git identity",
  provider: "GitHub",
  init_wizard: "New project",
  codex: "Codex parity",
  diagnostics: "Diagnostics",
  docs: "Docs",
  release_notes: "Release news",
};

export const MODULE_OPERATION_SUMMARIES: Record<ModuleKey, string> = {
  codegen: "Prose requests, the approval gate, and per-stage cost",
  evals: "Matrix runs, A/B verdicts, and benchmark definitions",
  project_gate: "Workspace selection and project context",
  home_overview: "Readiness, drift, and current priorities",
  project_dashboard: "Git and connected project systems",
  tools: "Inventory, versions, channels, and repairs",
  config_deploy: "Source drift, file diffs, and deployment",
  cleanup_restore: "Backups, cleanup, and recovery history",
  settings: "Inheritance, sources, and local overrides",
  mcp: "Connector scopes and live status",
  local_config: "Blueprints, previews, and project-local config",
  knowledge: "Graph, retrieval, packs, and evidence",
  services: "Bridges, runtimes, lifecycle, and logs",
  package_security: "Dependency findings and safe fixes",
  sessions: "Usage, cost, activity, and transcripts",
  scheduled_tasks: "Claude and Codex automation inventory",
  account: "Credentials, instructions, and runtime identity",
  doctor: "Configuration findings and repair routes",
  model_assignments: "Model pins and routing distribution",
  environment: "Curated values and redacted system state",
  git_identity: "Scoped identity and commit policy",
  provider: "Accounts, repositories, and clone runway",
  init_wizard: "Templates, staged files, and project handoff",
  codex: "Deployment and conversion parity",
  diagnostics: "Backend signals, audit, and live events",
  docs: "README summary and project reference documents",
  release_notes: "What shipped, where it lives, and how to use it",
};

export const MODULE_GROUP_ORDER: ModuleGroup[] = [
  "machine",
  "repo",
  "infrastructure",
  "agents",
  "reference",
];

// Matches setup/src/cabal/webapi/routers/system.py MODULE_KEYS exactly (same order).
// Health and drift are reported per key, so this list must not gain frontend-only pages.
// "codegen"/"evals" are staged here ahead of the backend addition landing (021-codegen-eval-
// modules Phase 1, T001-T003) — both have real backend availability endpoints per
// contracts/codegen-api.md and contracts/evals-api.md, so they belong in this list, not
// LOCAL_MODULE_KEYS. Reconcile with system.py's MODULE_KEYS when that lands.
export const BACKEND_MODULE_KEYS = [
  "project_gate",
  "home_overview",
  "project_dashboard",
  "tools",
  "config_deploy",
  "cleanup_restore",
  "settings",
  "mcp",
  "local_config",
  "knowledge",
  "services",
  "package_security",
  "sessions",
  "scheduled_tasks",
  "account",
  "doctor",
  "model_assignments",
  "environment",
  "git_identity",
  "provider",
  "init_wizard",
  "codex",
  "diagnostics",
  "docs",
  "codegen",
  "evals",
] as const;

/** Pages with no backend module; the sidebar shows them, health never reports on them. */
export const LOCAL_MODULE_KEYS = ["release_notes"] as const;

export const MODULE_KEYS = [...BACKEND_MODULE_KEYS, ...LOCAL_MODULE_KEYS] as const;

export type ModuleKey = (typeof MODULE_KEYS)[number];

export interface ModuleDefinition {
  key: ModuleKey;
  title: string;
  group: ModuleGroup;
  phase: number;
  component: ComponentType | LazyExoticComponent<ComponentType> | null;
}

export const MODULE_REGISTRY: ModuleDefinition[] = [
  {
    key: "project_gate",
    title: "Project Gate & Switcher",
    group: "repo",
    phase: 3,
    component: ProjectGateModule,
  },
  {
    key: "home_overview",
    title: "Home Overview",
    group: "machine",
    phase: 3,
    component: OverviewModule,
  },
  {
    key: "project_dashboard",
    title: "Project Dashboard",
    group: "repo",
    phase: 3,
    component: ProjectDashboardModule,
  },
  {
    key: "tools",
    title: "Tools Catalog",
    group: "machine",
    phase: 4,
    component: ToolsModule,
  },
  {
    key: "config_deploy",
    title: "Global Config Deployment",
    group: "agents",
    phase: 5,
    component: ConfigDeployModule,
  },
  {
    key: "cleanup_restore",
    title: "Cleanup & Restore",
    group: "agents",
    phase: 5,
    component: CleanupRestoreModule,
  },
  {
    key: "settings",
    title: "Settings Configurator",
    group: "agents",
    phase: 5,
    component: SettingsModule,
  },
  { key: "mcp", title: "MCP Connectors", group: "infrastructure", phase: 8, component: McpModule },
  {
    key: "local_config",
    title: "Local Project Config",
    group: "repo",
    phase: 5,
    component: LocalConfigModule,
  },
  {
    key: "knowledge",
    title: "Knowledge & Retrieval",
    group: "repo",
    phase: 7,
    component: KnowledgeModule,
  },
  {
    key: "services",
    title: "Agent Services",
    group: "infrastructure",
    phase: 8,
    component: ServicesModule,
  },
  {
    key: "package_security",
    title: "Package Security",
    group: "infrastructure",
    phase: 10,
    component: PackageSecurityModule,
  },
  {
    key: "sessions",
    title: "Sessions Dashboard",
    group: "repo",
    phase: 6,
    component: SessionsModule,
  },
  {
    key: "scheduled_tasks",
    title: "Scheduled Tasks",
    group: "agents",
    phase: 12,
    component: ScheduledTasksModule,
  },
  {
    key: "account",
    title: "Account & Assistant Info",
    group: "agents",
    phase: 6,
    component: AccountModule,
  },
  {
    key: "doctor",
    title: "Config Doctor",
    group: "agents",
    phase: 6,
    component: DoctorModule,
  },
  {
    key: "model_assignments",
    title: "Model Assignments",
    group: "agents",
    phase: 6,
    component: ModelAssignmentsModule,
  },
  {
    key: "environment",
    title: "Environment Variables",
    group: "machine",
    phase: 10,
    component: EnvironmentModule,
  },
  {
    key: "git_identity",
    title: "Git Identity & Commit Policy",
    group: "repo",
    phase: 10,
    component: GitIdentityModule,
  },
  {
    key: "provider",
    title: "Provider Repos & Clone",
    group: "infrastructure",
    phase: 9,
    component: ProviderModule,
  },
  {
    key: "init_wizard",
    title: "New Project Wizard",
    group: "repo",
    phase: 9,
    component: InitProjectModule,
  },
  { key: "codex", title: "Codex Parity", group: "agents", phase: 5, component: CodexModule },
  {
    key: "diagnostics",
    title: "Diagnostics & Backend Health",
    group: "machine",
    phase: 3,
    component: DiagnosticsModule,
  },
  {
    key: "docs",
    title: "Docs & README",
    group: "reference",
    phase: 11,
    component: DocsModule,
  },
  {
    key: "release_notes",
    title: "Release News",
    group: "reference",
    phase: 15,
    component: ReleaseNotesModule,
  },
  // 021-codegen-eval-modules Phase 1: registered ahead of their own build phase (US1 = Phase 3,
  // US2 = Phase 4 of that feature's tasks.md), routed to the shared ModuleUnavailable placeholder
  // via the existing `component: null` mechanism (research.md R8) until their module UI lands.
  {
    key: "codegen",
    title: ".NET Code Generation",
    group: "repo",
    phase: 16,
    component: null,
  },
  {
    key: "evals",
    title: "Agent Eval Harness",
    group: "agents",
    phase: 17,
    component: null,
  },
];

export const DEFAULT_MODULE_KEY: ModuleKey = "home_overview";

export function modulesByGroup(group: ModuleGroup): ModuleDefinition[] {
  return MODULE_REGISTRY.filter((module) => module.group === group);
}

export function findModule(key: string): ModuleDefinition | undefined {
  return MODULE_REGISTRY.find((module) => module.key === key);
}

export function requireModule(key: ModuleKey): ModuleDefinition {
  const module = findModule(key);
  if (module === undefined) throw new Error(`Module registry is missing required key: ${key}`);
  return module;
}
