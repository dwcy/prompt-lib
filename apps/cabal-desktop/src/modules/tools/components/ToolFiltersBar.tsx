// Console filter bar: search across tools/categories/badges plus Category/Status/Channel selects
// on the mock's grid, with the existing badge toggle chips preserved as a chip row underneath.
import type { ToolStatusState } from "@/api/tools";
import { formatInstallChannel } from "@/modules/tools/toolStatusPresentation";
import type { ToolFilters } from "@/modules/tools/toolsFilters";

export interface ToolFiltersBarProps {
  filters: ToolFilters;
  onChange: (updater: (current: ToolFilters) => ToolFilters) => void;
  categories: Array<{ name: string; count: number }>;
  channels: Array<{ value: string; count: number }>;
  statusCounts: Map<ToolStatusState, number>;
  badgeCounts: Map<string, number>;
  totalCount: number;
}

const STATUS_OPTIONS: ToolStatusState[] = [
  "installed",
  "update_available",
  "missing",
  "unsupported",
  "manual_required",
  "error",
];

export function ToolFiltersBar({
  filters,
  onChange,
  categories,
  channels,
  statusCounts,
  badgeCounts,
  totalCount,
}: ToolFiltersBarProps) {
  return (
    <div className="tools-console__filters-group">
      <div className="tools-console__filters">
        <input
          type="search"
          placeholder={`Search ${totalCount} tools, categories, badges…`}
          aria-label="Search tools"
          autoComplete="off"
          value={filters.search}
          onChange={(event) => {
            const search = event.target.value;
            onChange((current) => ({ ...current, search }));
          }}
        />

        <select
          aria-label="Filter by category"
          value={filters.category ?? ""}
          onChange={(event) => {
            const category = event.target.value.length > 0 ? event.target.value : null;
            onChange((current) => ({ ...current, category }));
          }}
        >
          <option value="">All categories</option>
          {categories.map((category) => (
            <option key={category.name} value={category.name}>
              {category.name} ({category.count})
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by status"
          value={filters.status ?? ""}
          onChange={(event) => {
            const value = event.target.value;
            const status = value.length > 0 ? (value as ToolStatusState) : null;
            onChange((current) => ({ ...current, status }));
          }}
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((status) => (
            <option key={status} value={status}>
              {status} ({statusCounts.get(status) ?? 0})
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by install channel"
          value={filters.channel ?? ""}
          onChange={(event) => {
            const channel = event.target.value.length > 0 ? event.target.value : null;
            onChange((current) => ({ ...current, channel }));
          }}
        >
          <option value="">All channels</option>
          {channels.map((channel) => (
            <option key={channel.value} value={channel.value}>
              {formatInstallChannel(channel.value)} ({channel.count})
            </option>
          ))}
        </select>
      </div>

      {badgeCounts.size > 0 ? (
        // biome-ignore lint/a11y/useSemanticElements: a toggle-chip filter group, not a form <fieldset>
        <div
          className="tools-console__badge-filters select-none"
          role="group"
          aria-label="Filter by badge"
        >
          {[...badgeCounts.entries()].map(([badge, count]) => (
            <button
              key={badge}
              type="button"
              aria-pressed={filters.badge === badge}
              className={
                filters.badge === badge
                  ? "tools-console__badge-chip tools-console__badge-chip--active"
                  : "tools-console__badge-chip"
              }
              onClick={() => {
                const nextBadge = filters.badge === badge ? null : badge;
                onChange((current) => ({ ...current, badge: nextBadge }));
              }}
            >
              {badge} ({count})
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
