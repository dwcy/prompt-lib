// Virtualized data table (TanStack Virtual): column defs, sticky header, row selection, click-to-sort.
import { useVirtualizer } from "@tanstack/react-virtual";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

export interface VirtualDataTableColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortAccessor?: (row: T) => string | number;
}

export type SortDirection = "asc" | "desc";
interface SortState {
  key: string;
  direction: SortDirection;
}

export interface VirtualDataTableProps<T> {
  rows: T[];
  columns: Array<VirtualDataTableColumn<T>>;
  getRowId: (row: T) => string;
  rowHeight?: number;
  selectedIds?: ReadonlySet<string>;
  onSelectRow?: (id: string, selected: boolean) => void;
  emptyMessage?: string;
  ariaLabel?: string;
}

const DEFAULT_ROW_HEIGHT = 36;

export function VirtualDataTable<T>({
  rows,
  columns,
  getRowId,
  rowHeight = DEFAULT_ROW_HEIGHT,
  selectedIds,
  onSelectRow,
  emptyMessage = "No records available",
  ariaLabel = "Data table",
}: VirtualDataTableProps<T>) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);
  const [sort, setSort] = useState<SortState | null>(null);

  const sortedRows = useMemo(() => sortRows(rows, columns, sort), [rows, columns, sort]);

  const virtualizer = useVirtualizer({
    count: sortedRows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowHeight,
    overscan: 8,
  });

  const selectedRowCount =
    selectedIds === undefined
      ? 0
      : rows.reduce((count, row) => count + (selectedIds.has(getRowId(row)) ? 1 : 0), 0);
  const allRowsSelected = rows.length > 0 && selectedRowCount === rows.length;

  useEffect(() => {
    if (selectAllRef.current === null) return;
    selectAllRef.current.indeterminate = selectedRowCount > 0 && !allRowsSelected;
  }, [allRowsSelected, selectedRowCount]);

  function toggleSort(columnKey: string): void {
    setSort((current) => nextSortState(current, columnKey));
  }

  return (
    // biome-ignore lint/a11y/useSemanticElements: virtualized grid uses positioned divs, not a native <table>
    <div
      ref={scrollRef}
      className="virtual-data-table"
      role="table"
      aria-label={ariaLabel}
      aria-rowcount={rows.length + 1}
      aria-colcount={columns.length + (onSelectRow ? 1 : 0)}
    >
      {/* biome-ignore lint/a11y/useSemanticElements: virtualized grid uses positioned divs, not a native <table> */}
      <div
        className="virtual-data-table__header select-none"
        role="row"
        aria-rowindex={1}
        tabIndex={-1}
      >
        {onSelectRow ? (
          // biome-ignore lint/a11y/useSemanticElements: virtualized grid cannot use native table cells.
          <span className="virtual-data-table__select-cell" role="columnheader" tabIndex={-1}>
            <input
              ref={selectAllRef}
              type="checkbox"
              aria-label={allRowsSelected ? "Clear row selection" : "Select all rows"}
              checked={allRowsSelected}
              disabled={rows.length === 0}
              onChange={(event) => {
                for (const row of rows) onSelectRow(getRowId(row), event.target.checked);
              }}
            />
          </span>
        ) : null}
        {columns.map((column) => {
          if (column.sortAccessor === undefined) {
            return (
              // biome-ignore lint/a11y/useSemanticElements: virtualized grid cannot use native table cells.
              <span
                key={column.key}
                role="columnheader"
                tabIndex={-1}
                className="virtual-data-table__header-cell virtual-data-table__header-cell--static"
              >
                {column.header}
              </span>
            );
          }

          const activeDirection = sort?.key === column.key ? sort.direction : null;
          return (
            // biome-ignore lint/a11y/useSemanticElements: virtualized grid uses div/button, not a native <table>
            <button
              key={column.key}
              type="button"
              role="columnheader"
              aria-sort={
                activeDirection === null
                  ? "none"
                  : activeDirection === "asc"
                    ? "ascending"
                    : "descending"
              }
              className="virtual-data-table__header-cell virtual-data-table__header-cell--sortable"
              onClick={() => toggleSort(column.key)}
            >
              {column.header}
              {activeDirection !== null ? (
                <span className="virtual-data-table__sort-mark" aria-hidden="true">
                  {activeDirection === "asc" ? " ↑" : " ↓"}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      {/* biome-ignore lint/a11y/useSemanticElements: virtualized rows require a positioned div container. */}
      <div
        className="virtual-data-table__body"
        role="rowgroup"
        style={sortedRows.length === 0 ? undefined : { height: virtualizer.getTotalSize() }}
      >
        {sortedRows.length === 0 ? (
          // biome-ignore lint/a11y/useSemanticElements: virtualized grid cannot use native table rows.
          <div className="virtual-data-table__empty" role="row" tabIndex={-1}>
            {/* biome-ignore lint/a11y/useSemanticElements: virtualized grid cannot use native table cells. */}
            <span role="cell" tabIndex={-1}>
              {emptyMessage}
            </span>
          </div>
        ) : null}
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const row = sortedRows[virtualRow.index];
          const rowId = getRowId(row);
          return (
            // biome-ignore lint/a11y/useSemanticElements: virtualized grid uses positioned divs, not a native <table>
            <div
              key={rowId}
              role="row"
              aria-rowindex={virtualRow.index + 2}
              tabIndex={-1}
              className="virtual-data-table__row"
              style={{ transform: `translateY(${virtualRow.start}px)`, height: virtualRow.size }}
            >
              {onSelectRow ? (
                // biome-ignore lint/a11y/useSemanticElements: virtualized grid uses positioned divs, not a native <table>
                <span className="virtual-data-table__select-cell" role="cell">
                  <input
                    type="checkbox"
                    aria-label={`Select ${rowId}`}
                    checked={selectedIds?.has(rowId) ?? false}
                    onChange={(event) => onSelectRow(rowId, event.target.checked)}
                  />
                </span>
              ) : null}
              {columns.map((column) => (
                // biome-ignore lint/a11y/useSemanticElements: virtualized grid uses positioned divs, not a native <table>
                <span key={column.key} role="cell" className="virtual-data-table__cell">
                  {column.render(row)}
                </span>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function sortRows<T>(
  rows: T[],
  columns: Array<VirtualDataTableColumn<T>>,
  sort: SortState | null,
): T[] {
  if (sort === null) return rows;
  const column = columns.find((candidate) => candidate.key === sort.key);
  if (column?.sortAccessor === undefined) return rows;
  const accessor = column.sortAccessor;
  const sorted = [...rows].sort((a, b) => compareValues(accessor(a), accessor(b)));
  return sort.direction === "asc" ? sorted : sorted.reverse();
}

function compareValues(left: string | number, right: string | number): number {
  if (typeof left === "number" && typeof right === "number") return left - right;
  return String(left).localeCompare(String(right));
}

function nextSortState(current: SortState | null, columnKey: string): SortState | null {
  if (current?.key !== columnKey) return { key: columnKey, direction: "asc" };
  if (current.direction === "asc") return { key: columnKey, direction: "desc" };
  return null;
}
