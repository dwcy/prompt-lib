// Tools Catalog: category rail + search/status/channel/badge filters w/ live counts, a virtualized
// table joining catalog metadata with async status fill-in, and a detail drawer with a version
// Select feeding the install/update action flow (T042).
import { useMemo, useState } from "react";
import { type ToolStatusState, useToolDetail, useToolsCatalog, useToolsStatus } from "@/api/tools";
import { DetailDrawer } from "@/components/DetailDrawer";
import { EmptyState } from "@/components/EmptyState";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { CategoryRail } from "@/modules/tools/components/CategoryRail";
import { ToolDetailContent } from "@/modules/tools/components/ToolDetailContent";
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

export function ToolsModule() {
  const catalogQuery = useToolsCatalog();
  const statusQuery = useToolsStatus();
  const [filters, setFilters] = useState<ToolFilters>(EMPTY_TOOL_FILTERS);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const detailQuery = useToolDetail(selectedKey);

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
  const readiness = toolReadiness(statusCounts, rows.length, statusQuery.isPending);

  return (
    <div className="tools-module">
      <CategoryRail
        categories={categories}
        total={rows.length}
        selected={filters.category}
        onSelect={(category) => setFilters((current) => ({ ...current, category }))}
      />

      <div className="tools-module__main">
        <section className="tools-readiness-strip">
          <div>
            <span className="us3-eyebrow">Toolchain readiness</span>
            <strong>{readiness.headline}</strong>
            <p>{readiness.summary}</p>
          </div>
          <div className="tools-readiness-strip__states">
            {readiness.states.map((state) => (
              <button
                key={state.status}
                type="button"
                onClick={() => setFilters((current) => ({ ...current, status: state.status }))}
                disabled={state.count === 0}
              >
                <StatePill variant={state.variant} label={state.label} />
                <span>{state.count}</span>
              </button>
            ))}
          </div>
        </section>

        <ToolFiltersBar
          filters={filters}
          onChange={setFilters}
          channels={channels}
          statusCounts={statusCounts}
          badgeCounts={badgeCounts}
        />

        <p className="tools-module__result-count select-none">
          {visibleRows.length} of {rows.length} tools
        </p>

        {visibleRows.length === 0 ? (
          <EmptyState title="No tools match these filters" body="Try clearing search or filters." />
        ) : (
          <ToolsTable rows={visibleRows} onSelectRow={setSelectedKey} />
        )}
      </div>

      <DetailDrawer
        isOpen={selectedKey !== null}
        onClose={() => setSelectedKey(null)}
        title={detailQuery.data?.label ?? selectedKey ?? undefined}
      >
        {detailQuery.isPending ? (
          <EmptyState title="Loading tool detail…" />
        ) : detailQuery.isError ? (
          <EmptyState title="Could not load tool detail" body={detailQuery.error.message} />
        ) : detailQuery.data !== undefined ? (
          <ToolDetailContent tool={detailQuery.data} />
        ) : null}
      </DetailDrawer>
    </div>
  );
}

function toolReadiness(
  statusCounts: Map<ToolStatusState, number>,
  total: number,
  isPending: boolean,
) {
  const installed = statusCounts.get("installed") ?? 0;
  const updates = statusCounts.get("update_available") ?? 0;
  const missing = statusCounts.get("missing") ?? 0;
  const manual = statusCounts.get("manual_required") ?? 0;
  const errors = statusCounts.get("error") ?? 0;
  const unsupported = statusCounts.get("unsupported") ?? 0;
  const attention = updates + missing + manual + errors;
  return {
    headline: isPending ? "Probing installed tools" : `${installed}/${total} ready`,
    summary:
      attention === 0
        ? `${unsupported} unsupported or intentionally unavailable tool(s).`
        : `${updates} update(s), ${missing} missing, ${manual} manual, ${errors} error(s).`,
    states: [
      {
        status: "update_available" as const,
        count: updates,
        variant: "update" as const,
        label: "updates",
      },
      { status: "missing" as const, count: missing, variant: "missing" as const, label: "missing" },
      {
        status: "manual_required" as const,
        count: manual,
        variant: "degraded" as const,
        label: "manual",
      },
      { status: "error" as const, count: errors, variant: "error" as const, label: "errors" },
    ] satisfies Array<{
      status: ToolStatusState;
      count: number;
      variant: StatePillVariant;
      label: string;
    }>,
  };
}
