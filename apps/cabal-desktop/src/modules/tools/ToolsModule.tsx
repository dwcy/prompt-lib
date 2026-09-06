// Tools console screen: search/category/status/channel/badge filter bar, three-pane layout
// (category rail | virtualized readiness table | sticky detail pane) with async status fill-in
// and the install/update confirm flow (T042/T043), per the cabal-console mock's isTools section.
import { useMemo, useState } from "react";
import { useToolsCatalog, useToolsStatus } from "@/api/tools";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { CategoryRail } from "@/modules/tools/components/CategoryRail";
import { ToolDetailPane } from "@/modules/tools/components/ToolDetailPane";
import { ToolFiltersBar } from "@/modules/tools/components/ToolFiltersBar";
import { ToolsTable } from "@/modules/tools/components/ToolsTable";
import {
  collectBadgeCounts,
  collectStatusCounts,
  EMPTY_TOOL_FILTERS,
  filterToolRows,
  joinToolsWithStatus,
  type ToolFilters,
} from "@/modules/tools/toolsFilters";
import "./ToolsModule.css";

export function ToolsModule() {
  const catalogQuery = useToolsCatalog();
  const statusQuery = useToolsStatus();
  const [filters, setFilters] = useState<ToolFilters>(EMPTY_TOOL_FILTERS);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const rows = useMemo(
    () => joinToolsWithStatus(catalogQuery.data?.items ?? [], statusQuery.data?.items ?? []),
    [catalogQuery.data, statusQuery.data],
  );
  const visibleRows = useMemo(() => filterToolRows(rows, filters), [rows, filters]);
  const badgeCounts = useMemo(() => collectBadgeCounts(rows), [rows]);
  const statusCounts = useMemo(() => collectStatusCounts(rows), [rows]);

  if (catalogQuery.isPending) {
    return <EmptyState title="Loading tools catalog…" />;
  }

  if (catalogQuery.isError) {
    return (
      <EmptyState title="Could not load the tools catalog" body={catalogQuery.error.message} />
    );
  }

  const categories = Object.entries(catalogQuery.data.category_counts).map(([name, count]) => ({
    name,
    count,
  }));
  const channels = Object.entries(catalogQuery.data.channel_counts).map(([value, count]) => ({
    value,
    count,
  }));
  // The detail pane is always populated (mock behavior): the explicit selection when it survives
  // the active filters, otherwise the first visible row.
  const visibleSelection = visibleRows.some((row) => row.key === selectedKey)
    ? selectedKey
    : (visibleRows[0]?.key ?? null);

  return (
    <div className="tools-console">
      <ToolFiltersBar
        filters={filters}
        onChange={setFilters}
        categories={categories}
        channels={channels}
        statusCounts={statusCounts}
        badgeCounts={badgeCounts}
        totalCount={rows.length}
      />

      <p className="tools-console__count select-none">
        {visibleRows.length} of {rows.length} tools
      </p>

      <CardRefreshFooter>
        <RefreshButton
          label="tools catalog"
          onRefresh={() => {
            void catalogQuery.refetch();
            void statusQuery.refetch();
          }}
          isFetching={catalogQuery.isFetching || statusQuery.isFetching}
        />
      </CardRefreshFooter>

      <div className="tools-console__panes">
        <CategoryRail
          categories={categories}
          total={rows.length}
          selected={filters.category}
          onSelect={(category) => setFilters((current) => ({ ...current, category }))}
        />

        {visibleRows.length === 0 ? (
          <EmptyState title="No tools match these filters" body="Try clearing search or filters." />
        ) : (
          <ToolsTable
            rows={visibleRows}
            selectedKey={visibleSelection}
            onSelectRow={setSelectedKey}
          />
        )}

        <ToolDetailPane toolKey={visibleSelection} />
      </div>
    </div>
  );
}
