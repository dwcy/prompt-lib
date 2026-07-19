// Console-layout view models for Overview: KPI row, state-to-tone mapping, signal lanes, and the
// activity feed — pure presentation mapping over overviewSummary's derived cards/actions.
import type { OverviewPayload } from "@/api/schemas";
import type { KpiDeltaTone } from "@/components/KpiCard";
import type { StatePillVariant } from "@/components/StatePill";
import type { ModuleKey } from "@/modules/registry";
import type { OverviewActionSummary, OverviewCardSummary } from "./overviewSummary";

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

export function deriveOverviewKpis(
  payload: OverviewPayload,
  cards: OverviewCardSummary[],
  actions: OverviewActionSummary[],
): OverviewKpi[] {
  const attention = actions.filter((action) => action.variant !== "ok");
  const driftCount = Number(payload.drift_flags.claude) + Number(payload.drift_flags.codex);
  const steadyCount = cards.filter((card) => !isAttentionVariant(card.stateVariant)).length;
  const attentionCards = cards.length - steadyCount;
  const sessionsCard = cards.find((card) => card.key === "recent_sessions");
  return [
    {
      key: "priorities",
      label: "Priorities",
      value: String(attention.length),
      delta: attention.length === 0 ? "steady" : "review queue",
      deltaTone: attention.length === 0 ? "ok" : "warning",
      hint:
        attention.length === 0
          ? "Core config and live sections are in sync."
          : (attention[0]?.summary ?? "Workspace signals need attention."),
    },
    {
      key: "drift",
      label: "Drift lanes",
      value: String(driftCount),
      unit: "/ 2",
      delta: driftCount === 0 ? "aligned" : "changed",
      deltaTone: driftCount === 0 ? "ok" : "warning",
      hint: `Claude ${payload.drift_flags.claude ? "drift" : "in sync"} · Codex ${
        payload.drift_flags.codex ? "drift" : "in sync"
      }`,
    },
    {
      key: "signals",
      label: "Live signals",
      value: String(cards.length),
      delta: `${steadyCount} steady`,
      deltaTone: steadyCount === cards.length ? "ok" : "info",
      hint:
        attentionCards === 0
          ? "All sections reporting healthy states."
          : `${attentionCards} ${attentionCards === 1 ? "section needs" : "sections need"} attention.`,
    },
    {
      key: "sessions",
      label: "Recent sessions",
      value: String(payload.recent_sessions.length),
      delta: "captured",
      deltaTone: "neutral",
      hint: sessionsCard?.headline ?? "No sessions recorded yet.",
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
