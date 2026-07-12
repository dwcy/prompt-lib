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
