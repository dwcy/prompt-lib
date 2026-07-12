// Table column definitions for the Tools catalog, reusing VirtualDataTable as-is. The "Tool" column's
// label is the click target that opens the detail drawer (VirtualDataTable has no native row-click).
import { StatePill } from "@/components/StatePill";
import { VirtualDataTable, type VirtualDataTableColumn } from "@/components/VirtualDataTable";
import { toStatePillVariant } from "@/modules/tools/toolStatusPresentation";
import type { ToolRow } from "@/modules/tools/toolsFilters";

export interface ToolsTableProps {
  rows: ToolRow[];
  onSelectRow: (key: string) => void;
}

export function ToolsTable({ rows, onSelectRow }: ToolsTableProps) {
  const columns: Array<VirtualDataTableColumn<ToolRow>> = [
    {
      key: "label",
      header: "Tool",
      sortAccessor: (row) => row.label,
      render: (row) => (
        <button
          type="button"
          className="tools-table__open-detail"
          onClick={() => onSelectRow(row.key)}
        >
          {row.label}
        </button>
      ),
    },
    {
      key: "category",
      header: "Category",
      sortAccessor: (row) => row.category,
      render: (row) => row.category,
    },
    {
      key: "install_channel",
      header: "Channel",
      sortAccessor: (row) => row.install_channel,
      render: (row) => row.install_channel,
    },
    {
      key: "status",
      header: "Status",
      sortAccessor: (row) => row.status?.state ?? "",
      render: (row) =>
        row.status === null ? (
          <StatePill variant="loading" label="checking…" />
        ) : (
          <StatePill variant={toStatePillVariant(row.status.state)} />
        ),
    },
    {
      key: "current_version",
      header: "Current",
      sortAccessor: (row) => row.status?.current_version ?? "",
      render: (row) => row.status?.current_version ?? "—",
    },
    {
      key: "latest_version",
      header: "Latest",
      sortAccessor: (row) => row.status?.latest_version ?? "",
      render: (row) => row.status?.latest_version ?? "—",
    },
  ];

  return (
    <div className="tools-table">
      <VirtualDataTable rows={rows} columns={columns} getRowId={(row) => row.key} />
    </div>
  );
}
