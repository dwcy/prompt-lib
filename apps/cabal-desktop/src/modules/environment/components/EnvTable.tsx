// Console table for environment variables built on the shared VirtualDataTable: ON toggle, mono
// variable name, description, value (plain text or an inline editor), and a state pill per row.
import type { EnvEntry } from "@/api/securityEnvironment";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { VirtualDataTable, type VirtualDataTableColumn } from "@/components/VirtualDataTable";
import { EnvToggleSwitch } from "@/modules/environment/components/EnvToggleSwitch";

export interface EnvTableRow {
  entry: EnvEntry;
  value: string;
  isOn: boolean;
  canToggle: boolean;
  editing: boolean;
  dirty: boolean;
  stateVariant: StatePillVariant;
  stateLabel: string;
  onToggle?: () => void;
  onChange?: (value: string) => void;
  onBrowse?: () => void;
  onRevert?: () => void;
}

export interface EnvTableProps {
  rows: EnvTableRow[];
  ariaLabel: string;
}

export function EnvTable({ rows, ariaLabel }: EnvTableProps) {
  const columns: Array<VirtualDataTableColumn<EnvTableRow>> = [
    {
      key: "on",
      header: "On",
      render: (row) => (
        <EnvToggleSwitch
          checked={row.isOn}
          disabled={!row.canToggle}
          label={`Toggle ${row.entry.name}`}
          onToggle={row.onToggle}
        />
      ),
    },
    {
      key: "name",
      header: "Variable",
      sortAccessor: (row) => row.entry.name,
      render: (row) => <code className="env-cell-name">{row.entry.name}</code>,
    },
    {
      key: "description",
      header: "Description",
      sortAccessor: (row) => row.entry.description,
      render: (row) => (
        <span className="env-cell-desc" title={row.entry.description || undefined}>
          {row.entry.description || "—"}
        </span>
      ),
    },
    {
      key: "value",
      header: "Value",
      render: (row) => <EnvValueCell row={row} />,
    },
    {
      key: "state",
      header: "State",
      sortAccessor: (row) => row.stateLabel,
      render: (row) => <StatePill variant={row.stateVariant} label={row.stateLabel} />,
    },
  ];

  return (
    <div className="env-console__table">
      <VirtualDataTable
        rows={rows}
        columns={columns}
        getRowId={(row) => row.entry.name}
        rowHeight={44}
        ariaLabel={ariaLabel}
        emptyMessage="No variables matched"
      />
    </div>
  );
}

function EnvValueCell({ row }: { row: EnvTableRow }) {
  if (!row.editing) {
    return <code className="env-cell-value">{row.value || "—"}</code>;
  }
  return (
    <div className="env-cell-editor">
      <input
        value={row.value}
        onChange={(event) => row.onChange?.(event.target.value)}
        spellCheck={false}
        aria-label={`${row.entry.name} value`}
      />
      {row.entry.is_path ? (
        <button type="button" onClick={row.onBrowse}>
          Browse
        </button>
      ) : null}
      {row.dirty ? (
        <button type="button" onClick={row.onRevert}>
          Revert
        </button>
      ) : null}
    </div>
  );
}
