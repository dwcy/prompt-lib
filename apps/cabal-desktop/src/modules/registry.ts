// Static registry of all 22 feature modules: nav grouping, title, delivery phase, and page component
// (or null pre-launch, routed to the shared ModuleUnavailable placeholder).
import type { ComponentType } from "react";

export type ModuleGroup =
  | "project"
  | "environment-setup"
  | "configuration"
  | "knowledge"
  | "operations"
  | "observability";

export const MODULE_GROUP_LABELS: Record<ModuleGroup, string> = {
  project: "Project",
  "environment-setup": "Environment Setup",
  configuration: "Configuration",
  knowledge: "Knowledge",
  operations: "Operations",
  observability: "Observability",
};

export const MODULE_GROUP_ORDER: ModuleGroup[] = [
  "project",
  "environment-setup",
  "configuration",
  "knowledge",
  "operations",
  "observability",
];

// Matches setup/src/cabal/webapi/routers/system.py MODULE_KEYS exactly (same order).
export const MODULE_KEYS = [
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
  "account",
  "doctor",
  "model_assignments",
  "environment",
  "git_identity",
  "provider",
  "init_wizard",
  "codex",
  "diagnostics",
] as const;

export type ModuleKey = (typeof MODULE_KEYS)[number];

export interface ModuleDefinition {
  key: ModuleKey;
  title: string;
  group: ModuleGroup;
  phase: number;
  component: ComponentType | null;
}

export const MODULE_REGISTRY: ModuleDefinition[] = [
  {
    key: "project_gate",
    title: "Project Gate & Switcher",
    group: "project",
    phase: 3,
    component: null,
  },
  { key: "home_overview", title: "Home Overview", group: "project", phase: 3, component: null },
  {
    key: "project_dashboard",
    title: "Project Dashboard",
    group: "project",
    phase: 3,
    component: null,
  },
  { key: "tools", title: "Tools Catalog", group: "environment-setup", phase: 4, component: null },
  {
    key: "config_deploy",
    title: "Global Config Deployment",
    group: "configuration",
    phase: 5,
    component: null,
  },
  {
    key: "cleanup_restore",
    title: "Cleanup & Restore",
    group: "configuration",
    phase: 5,
    component: null,
  },
  {
    key: "settings",
    title: "Settings Configurator",
    group: "configuration",
    phase: 5,
    component: null,
  },
  { key: "mcp", title: "MCP Connectors", group: "configuration", phase: 8, component: null },
  {
    key: "local_config",
    title: "Local Project Config",
    group: "configuration",
    phase: 5,
    component: null,
  },
  {
    key: "knowledge",
    title: "Knowledge & Retrieval",
    group: "knowledge",
    phase: 7,
    component: null,
  },
  { key: "services", title: "Agent Services", group: "operations", phase: 8, component: null },
  {
    key: "package_security",
    title: "Package Security",
    group: "operations",
    phase: 10,
    component: null,
  },
  {
    key: "sessions",
    title: "Sessions Dashboard",
    group: "observability",
    phase: 6,
    component: null,
  },
  {
    key: "account",
    title: "Account & Assistant Info",
    group: "observability",
    phase: 6,
    component: null,
  },
  { key: "doctor", title: "Config Doctor", group: "observability", phase: 6, component: null },
  {
    key: "model_assignments",
    title: "Model Assignments",
    group: "observability",
    phase: 6,
    component: null,
  },
  {
    key: "environment",
    title: "Environment Variables",
    group: "environment-setup",
    phase: 10,
    component: null,
  },
  {
    key: "git_identity",
    title: "Git Identity & Commit Policy",
    group: "environment-setup",
    phase: 10,
    component: null,
  },
  {
    key: "provider",
    title: "Provider Repos & Clone",
    group: "environment-setup",
    phase: 9,
    component: null,
  },
  {
    key: "init_wizard",
    title: "New Project Wizard",
    group: "environment-setup",
    phase: 9,
    component: null,
  },
  { key: "codex", title: "Codex Parity", group: "configuration", phase: 5, component: null },
  {
    key: "diagnostics",
    title: "Diagnostics & Backend Health",
    group: "observability",
    phase: 3,
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
