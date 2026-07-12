// Search box + install-channel/status <select> filters + badge toggle chips, each showing a live
// (client-computed, or server-provided for channel) count next to its label.
import type { ToolStatusState } from "@/api/tools";
import type { ToolFilters } from "@/modules/tools/toolsFilters";

export interface ToolFiltersBarProps {
  filters: ToolFilters;
  onChange: (updater: (current: ToolFilters) => ToolFilters) => void;
  channels: Array<{ value: string; count: number }>;
  statusCounts: Map<ToolStatusState, number>;
  badgeCounts: Map<string, number>;
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
  channels,
  statusCounts,
  badgeCounts,
}: ToolFiltersBarProps) {
  return (
    <div className="tools-filters-bar">
      <input
        type="search"
        className="tools-filters-bar__search"
        placeholder="Search tools…"
        aria-label="Search tools"
        value={filters.search}
        onChange={(event) => {
          const search = event.target.value;
          onChange((current) => ({ ...current, search }));
        }}
      />

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
            {channel.value} ({channel.count})
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

      {/* biome-ignore lint/a11y/useSemanticElements: a toggle-chip filter group, not a form <fieldset> */}
      <div
        className="tools-filters-bar__badges select-none"
        role="group"
        aria-label="Filter by badge"
      >
        {[...badgeCounts.entries()].map(([badge, count]) => (
          <button
            key={badge}
            type="button"
            aria-pressed={filters.badge === badge}
            className={filters.badge === badge ? "tools-filters-bar__badge--active" : undefined}
            onClick={() => {
              const nextBadge = filters.badge === badge ? null : badge;
              onChange((current) => ({ ...current, badge: nextBadge }));
            }}
          >
            {badge} ({count})
          </button>
        ))}
      </div>
    </div>
  );
}
