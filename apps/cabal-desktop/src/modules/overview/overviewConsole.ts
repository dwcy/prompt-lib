// Console-layout view models for Overview: KPI row, state-to-tone mapping, signal lanes, and the
// activity feed — pure presentation mapping over overviewSummary's derived cards/actions.
import type { KpiDeltaTone } from "@/components/KpiCard";
import type { StatePillVariant } from "@/components/StatePill";
import type { ModuleKey } from "@/modules/registry";
import type { OverviewActionSummary } from "./overviewSummary";

export type StatusTone = "ok" | "info" | "warning" | "danger" | "neutral";

export interface OverviewKpi {
  key: string;
  label: string;
  value: string;
  unit?: string;
  delta: string;
  deltaTone: KpiDeltaTone;
  hint: string;
}

export interface OverviewActivityItem {
  key: string;
  glyph: string;
  tone: StatusTone;
  title: string;
  summary: string;
  meta: string;
  module: ModuleKey;
}

export interface OverviewSignalLane {
  key: string;
  title: string;
  description: string;
  cardKeys: string[];
}

export const SIGNAL_LANES: OverviewSignalLane[] = [
  {
    key: "operational-core",
    title: "Operational core",
    description: "Project connectivity, recent work, and the active runtime identity.",
    cardKeys: ["dashboard_summary", "recent_sessions", "account"],
  },
  {
    key: "safeguards",
    title: "Safeguards",
    description: "Configuration integrity, retrieval readiness, and dependency risk.",
    cardKeys: ["doctor", "knowledge_availability", "security_summary"],
  },
];

const ATTENTION_VARIANTS: ReadonlySet<StatePillVariant> = new Set<StatePillVariant>([
  "failed",
  "unavailable",
  "degraded",
  "stale",
]);

export function isAttentionVariant(variant: StatePillVariant | null): boolean {
  return variant !== null && ATTENTION_VARIANTS.has(variant);
}

export function variantTone(variant: StatePillVariant | null): StatusTone {
  if (variant === null) return "neutral";
  switch (variant) {
    case "ok":
    case "installed":
    case "open":
    case "succeeded":
      return "ok";
    case "failed":
    case "error":
      return "danger";
    case "degraded":
    case "stale":
    case "missing":
      return "warning";
    case "unavailable":
    case "closed":
    case "cancelled":
    case "queued":
      return "neutral";
    default:
      return "info";
  }
}

export interface ToolCatalogSummary {
  total: number;
  installedCount: number;
  missingCount: number;
  manualCount: number;
  unsupportedCount: number;
}

export interface AgentKnowledgeSummary {
  nodes: number;
  edges: number;
  available: boolean;
  agentCount: number;
  skillCount: number;
  hookCount: number;
  ruleCount: number;
}

export interface ServicesReadySummary {
  ready: number;
  total: number;
  notReadyLabels: string[];
}

export function deriveOverviewKpis(
  tools: ToolCatalogSummary | null,
  knowledge: AgentKnowledgeSummary | null,
  services: ServicesReadySummary | null,
): OverviewKpi[] {
  const installedPercent =
    tools !== null && tools.total > 0
      ? Math.round((tools.installedCount / tools.total) * 100)
      : null;
  const assetTotal =
    knowledge !== null
      ? knowledge.agentCount + knowledge.skillCount + knowledge.hookCount + knowledge.ruleCount
      : null;

  return [
    {
      key: "tool_catalog",
      label: "Tool catalog",
      value: tools !== null ? String(tools.total) : "…",
      delta: installedPercent !== null ? `${installedPercent}% installed` : "loading",
      deltaTone: installedPercent === null ? "neutral" : installedPercent >= 90 ? "ok" : "info",
      hint:
        tools !== null
          ? `${tools.installedCount} installed · ${tools.missingCount} missing · ${tools.manualCount} manual · ${tools.unsupportedCount} n/a`
          : "Loading tool catalog…",
    },
    {
      key: "agent_assets",
      label: "Agent assets",
      value: assetTotal !== null ? String(assetTotal) : "…",
      delta: "~/.claude",
      deltaTone: "neutral",
      hint:
        knowledge !== null
          ? `${knowledge.agentCount} agents · ${knowledge.skillCount} skills · ${knowledge.hookCount} hooks · ${knowledge.ruleCount} rules`
          : "Loading knowledge graph…",
    },
    {
      key: "knowledge_graph",
      label: "Knowledge graph",
      value: knowledge !== null ? String(knowledge.nodes) : "…",
      unit: "nodes",
      delta: knowledge === null ? "loading" : knowledge.available ? "exported" : "not exported",
      deltaTone: knowledge === null ? "neutral" : knowledge.available ? "ok" : "warning",
      hint: knowledge !== null ? `${knowledge.edges} edges` : "Loading knowledge graph…",
    },
    {
      key: "services_ready",
      label: "Services ready",
      value: services !== null ? String(services.ready) : "…",
      unit: services !== null ? `/ ${services.total}` : undefined,
      delta:
        services === null
          ? "loading"
          : services.ready === services.total
            ? "all ready"
            : `${services.total - services.ready} need attention`,
      deltaTone:
        services === null ? "neutral" : services.ready === services.total ? "ok" : "warning",
      hint:
        services !== null
          ? services.notReadyLabels.length > 0
            ? services.notReadyLabels.join(" · ")
            : "All project services ready."
          : "Loading services…",
    },
  ];
}

const TONE_GLYPHS: Record<StatusTone, string> = {
  danger: "■",
  warning: "▲",
  info: "●",
  ok: "●",
  neutral: "●",
};

export function deriveActivityItems(actions: OverviewActionSummary[]): OverviewActivityItem[] {
  return actions.map((action) => {
    const tone = variantTone(action.variant);
    return {
      key: action.key,
      glyph: TONE_GLYPHS[tone],
      tone,
      title: action.title,
      summary: action.summary,
      meta: `${action.module} · ${action.label}`,
      module: action.module,
    };
  });
}
