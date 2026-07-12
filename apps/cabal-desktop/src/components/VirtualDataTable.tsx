// Virtualized data table (TanStack Virtual): column defs, sticky header, row selection, click-to-sort.
import { useVirtualizer } from "@tanstack/react-virtual";
import { type ReactNode, useMemo, useRef, useState } from "react";

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
}

const DEFAULT_ROW_HEIGHT = 36;

export function VirtualDataTable<T>({
  rows,
  columns,
  getRowId,
  rowHeight = DEFAULT_ROW_HEIGHT,
  selectedIds,
  onSelectRow,
}: VirtualDataTableProps<T>) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [sort, setSort] = useState<SortState | null>(null);

  const sortedRows = useMemo(() => sortRows(rows, columns, sort), [rows, columns, sort]);

  const virtualizer = useVirtualizer({
    count: sortedRows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowHeight,
    overscan: 8,
  });

  function toggleSort(columnKey: string): void {
    setSort((current) => nextSortState(current, columnKey));
  }

  return (
    // biome-ignore lint/a11y/useSemanticElements: virtualized grid uses positioned divs, not a native <table>
    <div ref={scrollRef} className="virtual-data-table" role="table">
      {/* biome-ignore lint/a11y/useSemanticElements: virtualized grid uses positioned divs, not a native <table> */}
      <div className="virtual-data-table__header select-none" role="row" tabIndex={-1}>
        {onSelectRow ? <span className="virtual-data-table__select-cell" /> : null}
        {columns.map((column) => (
          // biome-ignore lint/a11y/useSemanticElements: virtualized grid uses div/button, not a native <table>
          <button
            key={column.key}
            type="button"
            role="columnheader"
            className="virtual-data-table__header-cell"
            onClick={column.sortAccessor ? () => toggleSort(column.key) : undefined}
          >
            {column.header}
            {sort?.key === column.key ? (
              <span aria-hidden="true">{sort.direction === "asc" ? " ^" : " v"}</span>
            ) : null}
          </button>
        ))}
      </div>
      <div className="virtual-data-table__body" style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const row = sortedRows[virtualRow.index];
          const rowId = getRowId(row);
          return (
            // biome-ignore lint/a11y/useSemanticElements: virtualized grid uses positioned divs, not a native <table>
            <div
              key={rowId}
              role="row"
              tabIndex={-1}
              className="virtual-data-table__row"
              style={{ transform: `translateY(${virtualRow.start}px)`, height: virtualRow.size }}
            >
              {onSelectRow ? (
                // biome-ignore lint/a11y/useSemanticElements: virtualized grid uses positioned divs, not a native <table>
                <span className="virtual-data-table__select-cell" role="cell">
                  <input
                    type="checkbox"
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
