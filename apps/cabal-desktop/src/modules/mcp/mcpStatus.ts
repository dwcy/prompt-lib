// Shared MCP Connectors helpers: StatePill variant mapping, env-readiness summary, and the
// human-readable scope-ownership copy used by the table, detail panel, and scope-removal dialog
// so status logic lives in one place instead of being duplicated per component.
import type { McpServer } from "@/api/operations";
import type { StatePillVariant } from "@/components/StatePill";

export function mcpVariant(status: McpServer["status"]): StatePillVariant {
  switch (status) {
    case "connected":
      return "ok";
    case "pending":
      return "degraded";
    case "inactive":
      return "unavailable";
    case "error":
      return "error";
  }
}

export function mcpDotVariant(status: McpServer["status"]): "ok" | "warning" | "danger" | "muted" {
  switch (status) {
    case "connected":
      return "ok";
    case "pending":
      return "warning";
    case "error":
      return "danger";
    case "inactive":
      return "muted";
  }
}

export function envReadiness(server: McpServer): string {
  if (server.env_status.length === 0) return "—";
  const ready = server.env_status.filter((item) => item.present).length;
  return `${ready}/${server.env_status.length}`;
}

export type McpActionKind = "activate_global" | "activate_local" | "approve" | "disable";

export interface McpActionButton {
  kind: McpActionKind;
  label: string;
}

export function availableActions(server: McpServer): McpActionButton[] {
  const candidates: McpActionButton[] = [
    { kind: "activate_global", label: server.global_action_label },
    { kind: "activate_local", label: "Activate locally" },
    { kind: "approve", label: "Approve" },
    { kind: "disable", label: "Disable" },
  ];
  return candidates.filter((candidate) => server.actions_available.includes(candidate.kind));
}

export function scopeImpactCopy(scope: string): string {
  const normalized = scope.toLowerCase();
  if (normalized.includes("local") || normalized.includes("project")) {
    return "Owned by the active project; other workspaces are unaffected.";
  }
  if (normalized.includes("global") || normalized.includes("user")) {
    return "Owned by the user profile and inherited by every project.";
  }
  if (normalized.includes("plugin")) {
    return "Provided by an installed plugin and governed by that plugin lifecycle.";
  }
  if (normalized.includes("template")) {
    return "Declared by a reusable template rather than the current project.";
  }
  if (normalized.includes("remote") || normalized.includes("managed")) {
    return "Controlled outside this local workspace and retained here as reference.";
  }
  return "An independent configuration owner for this connector.";
}
