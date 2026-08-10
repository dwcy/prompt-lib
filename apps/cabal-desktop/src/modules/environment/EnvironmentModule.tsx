// Environment console: curated profile editor (toggle/edit/apply) and a read-only searchable
// system inventory, laid out as the single flat toggle table from the cabal-console mock.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { queryKeys } from "@/api/queryKeys";
import { type EnvEntry, type EnvScope, useEnvironment } from "@/api/securityEnvironment";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { useAction } from "@/hooks/useAction";
import { EnvScopeSwitcher } from "@/modules/environment/components/EnvScopeSwitcher";
import { EnvTable, type EnvTableRow } from "@/modules/environment/components/EnvTable";
import {
  countActive,
  sourceVariant,
  systemEntryLabel,
  systemEntryVariant,
} from "@/modules/environment/environmentPresentation";
import { useEnvironmentProfile } from "@/modules/environment/hooks/useEnvironmentProfile";
import "./EnvironmentModule.css";

type CuratedLane = "all" | "paths" | "runtime";

const LANES: Array<{ key: CuratedLane; label: string }> = [
  { key: "all", label: "All" },
  { key: "paths", label: "Filesystem" },
  { key: "runtime", label: "Runtime" },
];

export function EnvironmentModule() {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<EnvScope>("curated");
  const [lane, setLane] = useState<CuratedLane>("all");
  const [queryText, setQueryText] = useState("");
  const envQuery = useEnvironment(scope, scope === "system" ? queryText : "");
  const applyAction = useAction("env.apply");
  const profile = useEnvironmentProfile(scope, envQuery.data?.entries);

  useEffect(() => {
    if (applyAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("environment") });
  }, [applyAction.phase, queryClient]);

  if (envQuery.isPending) return <EmptyState title="Loading environment..." />;
  if (envQuery.isError) {
    return <EmptyState title="Environment unavailable" body={envQuery.error.message} />;
  }

  const normalizedQuery = queryText.trim().toLocaleLowerCase();
  const visibleEntries = envQuery.data.entries.filter((entry) => {
    const matchesQuery =
      normalizedQuery.length === 0 ||
      entry.name.toLocaleLowerCase().includes(normalizedQuery) ||
      entry.description.toLocaleLowerCase().includes(normalizedQuery);
    const matchesLane = lane === "all" || (lane === "paths" ? entry.is_path : !entry.is_path);
    return matchesQuery && (scope === "system" || matchesLane);
  });
  const enabledCount =
    scope === "curated"
      ? countActive(envQuery.data.entries, (entry) => profile.draft[entry.name] ?? "")
      : countActive(envQuery.data.entries, (entry) => entry.value_redacted);
  const rows: EnvTableRow[] = visibleEntries.map((entry) =>
    scope === "curated" ? curatedRow(entry, profile) : systemRow(entry),
  );

  return (
    <div className="env-console">
      <div className="env-intro">
        <span>
          {scope === "curated"
            ? "Curated variables are read from the system environment; toggles clear or restore a value before you apply it."
            : "System-inherited values are shown read-only; use search to filter by name or description."}
        </span>
        <span className="env-intro__summary">
          {enabledCount} enabled / {envQuery.data.count} total
        </span>
      </div>

      <EnvScopeSwitcher
        scope={scope}
        onScopeChange={setScope}
        queryText={queryText}
        onQueryChange={setQueryText}
        platform={envQuery.data.platform}
      />

      {profile.browseError !== null ? <p className="inline-error">{profile.browseError}</p> : null}

      {scope === "curated" ? (
        <div className="env-lanes" role="tablist" aria-label="Variable groups">
          {LANES.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={lane === item.key}
              className={lane === item.key ? "is-active" : ""}
              onClick={() => setLane(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}

      <EnvTable
        rows={rows}
        ariaLabel={
          scope === "curated" ? "Curated environment variables" : "System environment variables"
        }
      />

      {scope === "curated" ? (
        <div className="env-footer">
          <span>
            {profile.dirtyCount === 0 ? "Profile unchanged" : `${profile.dirtyCount} staged`}
          </span>
          <button type="button" disabled={profile.dirtyCount === 0} onClick={profile.revertAll}>
            Revert all
          </button>
          <button
            type="button"
            disabled={profile.dirtyCount === 0 || applyAction.phase === "preparing"}
            onClick={() => applyAction.prepare({ values: profile.dirtyValues })}
          >
            Apply {profile.dirtyCount}
          </button>
        </div>
      ) : null}

      <ConfirmDialog
        isOpen={applyAction.phase !== "idle" && applyAction.phase !== "succeeded"}
        actionTitle="Apply environment values"
        ticket={applyAction.ticket}
        phase={applyAction.phase}
        reviewNotice={applyAction.reviewNotice}
        error={applyAction.error}
        onConfirm={applyAction.confirm}
        onCancel={applyAction.reset}
      />
    </div>
  );
}

function curatedRow(
  entry: EnvEntry,
  profile: ReturnType<typeof useEnvironmentProfile>,
): EnvTableRow {
  const value = profile.draft[entry.name] ?? "";
  const dirty = entry.name in profile.dirtyValues;
  const isOn = value.trim() !== "";
  return {
    entry,
    value,
    isOn,
    canToggle: entry.editable,
    editing: entry.editable && isOn,
    dirty,
    stateVariant: dirty ? "update" : sourceVariant(entry.source),
    stateLabel: dirty ? "staged" : entry.source,
    onToggle: entry.editable ? () => profile.toggleEntry(entry) : undefined,
    onChange: entry.editable ? (next) => profile.setValue(entry.name, next) : undefined,
    onBrowse: entry.editable ? () => void profile.browseFor(entry) : undefined,
    onRevert: entry.editable ? () => profile.revertOne(entry.name) : undefined,
  };
}

function systemRow(entry: EnvEntry): EnvTableRow {
  return {
    entry,
    value: entry.value_redacted || "not reported",
    isOn: entry.value_redacted.trim() !== "",
    canToggle: false,
    editing: false,
    dirty: false,
    stateVariant: systemEntryVariant(entry),
    stateLabel: systemEntryLabel(entry),
  };
}
