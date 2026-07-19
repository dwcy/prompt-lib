// Virtualized tool readiness ledger. Rows describe capability, delivery lane, version movement,
// and live readiness instead of exposing catalog/status payload fields as a generic table.
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
      key: "capability",
      header: "Capability",
      sortAccessor: (row) => row.label,
      render: (row) => (
        <span className="tools-ledger__identity">
          <button
            type="button"
            className="tools-table__open-detail"
            onClick={() => onSelectRow(row.key)}
          >
            {row.label}
          </button>
          <small>{row.description}</small>
          <span>
            <strong>{row.category}</strong>
            {row.badges.slice(0, 2).map((badge) => (
              <i key={badge}>{badge}</i>
            ))}
          </span>
        </span>
      ),
    },
    {
      key: "delivery",
      header: "Delivery lane",
      sortAccessor: (row) => row.install_channel,
      render: (row) => (
        <span className="tools-ledger__delivery">
          <small>Install channel</small>
          <strong>{formatChannel(row.install_channel)}</strong>
          <span>{formatSourceState(row.source_state)}</span>
        </span>
      ),
    },
    {
      key: "versions",
      header: "Version route",
      sortAccessor: (row) => row.status?.current_version ?? "",
      render: (row) => (
        <span className="tools-ledger__versions">
          <span>
            <small>Current</small>
            <strong>{row.status?.current_version ?? "not installed"}</strong>
          </span>
          <i aria-hidden="true">-&gt;</i>
          <span>
            <small>Latest</small>
            <strong>{row.status?.latest_version ?? "not reported"}</strong>
          </span>
        </span>
      ),
    },
    {
      key: "readiness",
      header: "Readiness",
      sortAccessor: (row) => row.status?.state ?? "",
      render: (row) =>
        row.status === null ? (
          <span className="tools-ledger__readiness">
            <StatePill variant="loading" label="checking..." />
            <small>Status probe in progress</small>
          </span>
        ) : (
          <span className="tools-ledger__readiness">
            <StatePill variant={toStatePillVariant(row.status.state)} />
            <small>{formatCheckedAt(row.status.checked_at)}</small>
          </span>
        ),
    },
  ];

  return (
    <div className="tools-table tools-readiness-ledger">
      <VirtualDataTable
        rows={rows}
        columns={columns}
        getRowId={(row) => row.key}
        rowHeight={84}
        ariaLabel="Toolchain readiness ledger"
      />
    </div>
  );
}

function formatChannel(value: string) {
  return value.replaceAll("_", " ");
}

function formatSourceState(value: string) {
  if (value === "verified") return "Verified source";
  if (value === "manual_required") return "Manual source review";
  return "Source unavailable";
}

function formatCheckedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Probe time unavailable";
  return `Checked ${date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
}
