// Pure helpers for the Tools module: joins catalog metadata with the (slower, separately-fetched)
// status sweep so statuses can "fill in" after the table renders, plus client-side search/badge/
// status filtering and live counts that the backend doesn't compute for us (category/channel counts
// come straight from the catalog route instead — see ToolsModule).
import type { ToolCatalogItem, ToolStatus, ToolStatusEntry, ToolStatusState } from "@/api/tools";

export interface ToolRow extends ToolCatalogItem {
  status: ToolStatus | null;
}

export interface ToolFilters {
  category: string | null;
  channel: string | null;
  status: ToolStatusState | null;
  badge: string | null;
  search: string;
}

export const EMPTY_TOOL_FILTERS: ToolFilters = {
  category: null,
  channel: null,
  status: null,
  badge: null,
  search: "",
};

// A catalog item has no matching status until the (independent, slower) status sweep resolves —
// `status: null` is the async fill-in's "not yet arrived" marker, distinct from any server-reported
// ToolStatus.state (which is always definitive, never `loading`, per the tools contract).
export function joinToolsWithStatus(
  items: ToolCatalogItem[],
  statusEntries: ToolStatusEntry[],
): ToolRow[] {
  const statusByKey = new Map(statusEntries.map((entry) => [entry.key, entry]));
  return items.map((item) => ({ ...item, status: statusByKey.get(item.key) ?? null }));
}

export function filterToolRows(rows: ToolRow[], filters: ToolFilters): ToolRow[] {
  const search = filters.search.trim().toLowerCase();
  return rows.filter((row) => {
    if (filters.category !== null && row.category !== filters.category) return false;
    if (filters.channel !== null && row.install_channel !== filters.channel) return false;
    if (filters.status !== null && row.status?.state !== filters.status) return false;
    if (filters.badge !== null && !row.badges.includes(filters.badge)) return false;
    if (search.length === 0) return true;
    // Haystack mirrors the search placeholder's promise: tools, categories, badges (+ channel/key).
    const haystack =
      `${row.label} ${row.description} ${row.key} ${row.category} ${row.install_channel} ${row.badges.join(" ")}`.toLowerCase();
    return haystack.includes(search);
  });
}

export function collectBadgeCounts(rows: ToolRow[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const row of rows) {
    for (const badge of row.badges) counts.set(badge, (counts.get(badge) ?? 0) + 1);
  }
  return counts;
}

export function collectStatusCounts(rows: ToolRow[]): Map<ToolStatusState, number> {
  const counts = new Map<ToolStatusState, number>();
  for (const row of rows) {
    if (row.status === null) continue;
    counts.set(row.status.state, (counts.get(row.status.state) ?? 0) + 1);
  }
  return counts;
}
