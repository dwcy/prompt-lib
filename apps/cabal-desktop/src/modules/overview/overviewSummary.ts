// Derives the six Overview card summaries (headline/count/state) from the permissive section
// payloads — see api/schemas.ts's overviewSectionSchema doc comment for why the shapes aren't
// concretely typed by the web-api contract.
import type { OverviewPayload, OverviewSection } from "@/api/schemas";
import type { StatePillVariant } from "@/components/StatePill";
import { readNumber, readString } from "@/lib/unknownFields";
import type { ModuleKey } from "@/modules/registry";

export interface OverviewCardSummary {
  key: string;
  title: string;
  deepLinkModule: ModuleKey;
  headline: string | null;
  count: number | null;
  stateVariant: StatePillVariant | null;
}

export interface OverviewActionSummary {
  key: string;
  title: string;
  summary: string;
  module: ModuleKey;
  variant: StatePillVariant;
  label: string;
}

const KNOWN_STATE_VARIANTS: ReadonlySet<string> = new Set<StatePillVariant>([
  "ok",
  "loading",
  "degraded",
  "failed",
  "stale",
  "unavailable",
]);

function sectionState(section: OverviewSection): StatePillVariant | null {
  const raw = readString(section, ["state", "status"]);
  return raw !== null && KNOWN_STATE_VARIANTS.has(raw) ? (raw as StatePillVariant) : null;
}

function sectionHeadline(section: OverviewSection): string | null {
  return readString(section, ["summary", "headline", "message", "detail", "name"]);
}

function sectionCount(section: OverviewSection): number | null {
  return readNumber(section, ["count", "total"]);
}

export function deriveOverviewCards(payload: OverviewPayload): OverviewCardSummary[] {
  const latestSession = payload.recent_sessions[0];
  return [
    {
      key: "dashboard_summary",
      title: "Project Dashboard",
      deepLinkModule: "project_dashboard",
      headline: sectionHeadline(payload.dashboard_summary),
      count: sectionCount(payload.dashboard_summary),
      stateVariant: sectionState(payload.dashboard_summary),
    },
    {
      key: "recent_sessions",
      title: "Recent Sessions",
      deepLinkModule: "sessions",
      headline: latestSession !== undefined ? sectionHeadline(latestSession) : null,
      count: payload.recent_sessions.length,
      stateVariant: null,
    },
    {
      key: "account",
      title: "Account",
      deepLinkModule: "account",
      headline: sectionHeadline(payload.account),
      count: sectionCount(payload.account),
      stateVariant: sectionState(payload.account),
    },
    {
      key: "doctor",
      title: "Config Doctor",
      deepLinkModule: "doctor",
      headline: sectionHeadline(payload.doctor),
      count: sectionCount(payload.doctor),
      stateVariant: sectionState(payload.doctor),
    },
    {
      key: "knowledge_availability",
      title: "Knowledge & Retrieval",
      deepLinkModule: "knowledge",
      headline: sectionHeadline(payload.knowledge_availability),
      count: sectionCount(payload.knowledge_availability),
      stateVariant: sectionState(payload.knowledge_availability),
    },
    {
      key: "security_summary",
      title: "Package Security",
      deepLinkModule: "package_security",
      headline: sectionHeadline(payload.security_summary),
      count: sectionCount(payload.security_summary),
      stateVariant: sectionState(payload.security_summary),
    },
  ];
}

export function deriveOverviewActions(
  payload: OverviewPayload,
  cards: OverviewCardSummary[],
): OverviewActionSummary[] {
  const actions: OverviewActionSummary[] = [];
  if (payload.drift_flags.claude) {
    actions.push({
      key: "claude-drift",
      title: "Claude config drift",
      summary: "Claude deployment has repo changes waiting for review.",
      module: "config_deploy",
      variant: "degraded",
      label: "review",
    });
  }
  if (payload.drift_flags.codex) {
    actions.push({
      key: "codex-drift",
      title: "Codex parity drift",
      summary: "Codex assets need a deploy or conversion check.",
      module: "codex",
      variant: "degraded",
      label: "review",
    });
  }
  for (const card of cards) {
    if (
      card.stateVariant === "failed" ||
      card.stateVariant === "unavailable" ||
      card.stateVariant === "degraded" ||
      card.stateVariant === "stale"
    ) {
      actions.push({
        key: card.key,
        title: card.title,
        summary: card.headline ?? `${card.title} needs attention.`,
        module: card.deepLinkModule,
        variant: card.stateVariant,
        label: card.stateVariant,
      });
    }
  }
  if (actions.length === 0) {
    actions.push({
      key: "dashboard",
      title: "Project dashboard",
      summary: "Project services are ready for a quick scan.",
      module: "project_dashboard",
      variant: "ok",
      label: "steady",
    });
  }
  return actions
    .sort((left, right) => ACTION_PRIORITY[left.variant] - ACTION_PRIORITY[right.variant])
    .slice(0, 4);
}

const ACTION_PRIORITY: Record<StatePillVariant, number> = {
  failed: 0,
  error: 0,
  unavailable: 1,
  degraded: 2,
  stale: 3,
  missing: 3,
  update: 4,
  connecting: 4,
  loading: 4,
  queued: 4,
  running: 4,
  cancelled: 4,
  closed: 5,
  open: 5,
  installed: 5,
  succeeded: 5,
  ok: 5,
};
