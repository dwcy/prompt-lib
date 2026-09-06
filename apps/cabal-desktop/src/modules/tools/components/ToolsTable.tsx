// Virtualized tools ledger skinned to the console mock: status dot | tool | category | channel |
// status columns on a shared grid; the whole row (stretched button) opens the detail pane.
import { VirtualDataTable, type VirtualDataTableColumn } from "@/components/VirtualDataTable";
import { formatInstallChannel } from "@/modules/tools/toolStatusPresentation";
import type { ToolRow } from "@/modules/tools/toolsFilters";

export interface ToolsTableProps {
  rows: ToolRow[];
  selectedKey: string | null;
  onSelectRow: (key: string) => void;
}

const ROW_HEIGHT = 34;

export function ToolsTable({ rows, selectedKey, onSelectRow }: ToolsTableProps) {
  const columns: Array<VirtualDataTableColumn<ToolRow>> = [
    {
      key: "dot",
      header: "",
      render: (row) => (
        <span
          className={`tools-console__dot tools-console__dot--${row.status?.state ?? "pending"}`}
          aria-hidden="true"
        />
      ),
    },
    {
      key: "tool",
      header: "Tool",
      sortAccessor: (row) => row.label,
      render: (row) => (
        <button
          type="button"
          className="tools-console__row-open"
          aria-pressed={row.key === selectedKey}
          onClick={() => onSelectRow(row.key)}
        >
          {row.label}
          {row.badges.length > 0 ? (
            <span
              className="tools-console__badge-mark"
              role="img"
              aria-label={`Badges: ${row.badges.join(", ")}`}
            >
              ★
            </span>
          ) : null}
        </button>
      ),
    },
    {
      key: "category",
      header: "Category",
      sortAccessor: (row) => row.category,
      render: (row) => <span className="tools-console__cell-category">{row.category}</span>,
    },
    {
      key: "channel",
      header: "Channel",
      sortAccessor: (row) => row.install_channel,
      render: (row) => (
        <span className="tools-console__cell-mono">
          {formatInstallChannel(row.install_channel)}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortAccessor: (row) => row.status?.state ?? "",
      render: (row) =>
        row.status === null ? (
          <span className="tools-console__cell-status tools-console__cell-status--pending">
            checking…
          </span>
        ) : (
          <span
            className={`tools-console__cell-status tools-console__cell-status--${row.status.state}`}
          >
            {row.status.state}
          </span>
        ),
    },
  ];

  return (
    <div className="tools-console__table">
      <VirtualDataTable
        rows={rows}
        columns={columns}
        getRowId={(row) => row.key}
        rowHeight={ROW_HEIGHT}
        ariaLabel="Tools catalog"
      />
    </div>
  );
}
