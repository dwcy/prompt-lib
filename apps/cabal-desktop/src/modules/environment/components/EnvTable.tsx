// Console table for environment variables built on the shared VirtualDataTable: ON toggle, mono
// variable name, description, masked-aware value, secret marker, and semantic state text per row.
import { useEffect, useState } from "react";
import type { EnvEntry } from "@/api/securityEnvironment";
import type { StatePillVariant } from "@/components/StatePill";
import { ToggleSwitch } from "@/components/ToggleSwitch";
import { VirtualDataTable, type VirtualDataTableColumn } from "@/components/VirtualDataTable";

export interface EnvTableRow {
  entry: EnvEntry;
  value: string;
  isOn: boolean;
  canToggle: boolean;
  editing: boolean;
  dirty: boolean;
  isSecret: boolean;
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
        <ToggleSwitch
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
      key: "secret",
      header: "Secret",
      sortAccessor: (row) => (row.isSecret ? "secret" : "standard"),
      render: (row) => (
        <span
          className={`env-secret${row.isSecret ? " env-secret--masked" : ""}`}
          title={row.isSecret ? "Secret value; masked" : "Not a secret"}
        >
          {row.isSecret ? "secret" : "—"}
        </span>
      ),
    },
    {
      key: "state",
      header: "State",
      sortAccessor: (row) => row.stateLabel,
      render: (row) => (
        <span className="env-state" data-state={row.stateVariant}>
          {row.stateLabel}
        </span>
      ),
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
  const [secretVisible, setSecretVisible] = useState(false);

  useEffect(() => {
    if (!row.editing) setSecretVisible(false);
  }, [row.editing]);

  if (!row.editing) {
    const value = row.isSecret && row.value ? "••••••••••••" : row.value || "—";
    return (
      <code className={`env-cell-value${row.isSecret ? " env-cell-value--masked" : ""}`}>
        {value}
      </code>
    );
  }
  return (
    <div className="env-cell-editor">
      <div className={`env-cell-input${row.isSecret ? " env-cell-input--secret" : ""}`}>
        <input
          type={row.isSecret && !secretVisible ? "password" : "text"}
          value={row.value}
          onChange={(event) => row.onChange?.(event.target.value)}
          spellCheck={false}
          autoComplete="off"
          aria-label={`${row.entry.name} value`}
        />
        {row.isSecret ? (
          <button
            type="button"
            className="env-secret-visibility"
            aria-label={`${secretVisible ? "Hide" : "Show"} ${row.entry.name} secret`}
            aria-pressed={secretVisible}
            title={secretVisible ? "Hide secret" : "Show secret"}
            onClick={() => setSecretVisible((visible) => !visible)}
          >
            {secretVisible ? <EyeOffIcon /> : <EyeIcon />}
          </button>
        ) : null}
      </div>
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

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.1 12s3.6-7 9.9-7 9.9 7 9.9 7-3.6 7-9.9 7-9.9-7-9.9-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m3 3 18 18" />
      <path d="M10.6 5.2A10.8 10.8 0 0 1 12 5c6.3 0 9.9 7 9.9 7a15.7 15.7 0 0 1-2.2 3.1M6.6 6.6C3.7 8.5 2.1 12 2.1 12s3.6 7 9.9 7c1.9 0 3.6-.6 5-1.5" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </svg>
  );
}
