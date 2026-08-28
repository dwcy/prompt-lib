// Pure presentation helpers for the Sessions module: sort/lens/tab constants, formatters,
// and payload-shape utilities shared by the table, drawer, and detail components.
import type { SessionDetail, SessionSummary } from "@/api/observability";

export type SessionSort = "date_desc" | "cost_desc" | "tokens_desc" | "duration_desc";
export type SessionLens = "all" | "errors" | "writes" | "agents";
export type DetailTab = SessionDetail["tab"];

export const SESSION_SORTS: Array<{ value: SessionSort; label: string }> = [
  { value: "date_desc", label: "Recent" },
  { value: "cost_desc", label: "Cost" },
  { value: "tokens_desc", label: "Tokens" },
  { value: "duration_desc", label: "Duration" },
];

export const SESSION_LENSES: SessionLens[] = ["all", "errors", "writes", "agents"];

export const DETAIL_TABS: DetailTab[] = ["overview", "activity", "raw", "triggers"];

export function compactId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

export function sessionTitle(session: SessionSummary): string {
  const title = session.title;
  return title !== undefined && title !== null && title !== ""
    ? title
    : compactId(session.session_id);
}

// Pinned to en-US: this is a local dev tool, and number/currency formatting must stay stable
// across host machines regardless of OS locale (Intl.NumberFormat(undefined, ...) would silently
// render "1 000" / "0,00 US$" style output on non-English-locale systems).
const FORMAT_LOCALE = "en-US";

export function formatTokens(value: number): string {
  return Intl.NumberFormat(FORMAT_LOCALE, { notation: "compact" }).format(value);
}

export function formatCount(value: number): string {
  return Intl.NumberFormat(FORMAT_LOCALE).format(value);
}

export function formatMoney(value: number): string {
  return Intl.NumberFormat(FORMAT_LOCALE, { style: "currency", currency: "USD" }).format(value);
}

/**
 * Hint line for the cost card. Names the models the backend could not price so an
 * understated total is legible, and otherwise dates the rate table it was computed from.
 */
export function pricingHint(unpricedModels: string[], pricingAsOf: string | null): string {
  if (unpricedModels.length > 0) {
    return `Excludes ${unpricedModels.join(", ")} — no rate in the pricing table`;
  }
  return pricingAsOf !== null ? `Rates as of ${pricingAsOf}` : "";
}

export function formatDuration(value: number): string {
  if (value < 60) return `${Math.round(value)}s`;
  if (value < 3600) return `${Math.round(value / 60)}m`;
  return `${(value / 3600).toFixed(1)}h`;
}

export function formatWallHours(seconds: number): string {
  const hours = seconds / 3600;
  return hours >= 10 ? String(Math.round(hours)) : hours.toFixed(1);
}

export function formatSessionTime(value: string | null): string {
  if (value === null) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(FORMAT_LOCALE, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function sessionMatchesLens(session: SessionSummary, lens: SessionLens): boolean {
  if (lens === "errors") return session.tool_error_count > 0;
  if (lens === "writes") return session.files_written > 0;
  if (lens === "agents") return session.agent_count > 0;
  return true;
}

export function sessionLensCounts(sessions: SessionSummary[]): Record<SessionLens, number> {
  return {
    all: sessions.length,
    errors: sessions.filter((session) => session.tool_error_count > 0).length,
    writes: sessions.filter((session) => session.files_written > 0).length,
    agents: sessions.filter((session) => session.agent_count > 0).length,
  };
}

export function arrayFrom(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> => typeof item === "object" && item !== null,
      )
    : [];
}

export function numberValue(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

export function eventKey(row: Record<string, unknown>): string {
  return String(
    row.timestamp ??
      row.tool_name ??
      row.tool ??
      row.skill_name ??
      row.agent_type ??
      row.path ??
      JSON.stringify(row),
  );
}

export interface DispatchRow {
  name: string;
  calls: number;
}

/** Rolls raw activity agent rows (one per Task dispatch) up to per-agent-type call counts. */
export function aggregateDispatches(rows: Array<Record<string, unknown>>): DispatchRow[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const name =
      typeof row.agent_type === "string" && row.agent_type !== "" ? row.agent_type : "unknown";
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  const rolled = [...counts.entries()].map(([name, calls]) => ({ name, calls }));
  rolled.sort((a, b) => b.calls - a.calls || a.name.localeCompare(b.name));
  return rolled;
}
