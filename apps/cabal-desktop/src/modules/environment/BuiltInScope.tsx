// The pre-existing Curated and System views, unchanged in behaviour by the multi-source
// browser (FR-002) — extracted from EnvironmentModule so that file owns tab orchestration
// only and both stay inside the component size budget.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { queryKeys } from "@/api/queryKeys";
import { type EnvEntry, type EnvScope, useEnvironment } from "@/api/securityEnvironment";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { useAction } from "@/hooks/useAction";
import { EnvScopeSwitcher } from "@/modules/environment/components/EnvScopeSwitcher";
import { EnvTable, type EnvTableRow } from "@/modules/environment/components/EnvTable";
import {
  countActive,
  isSensitiveEnvironmentEntry,
  sourceLabel,
  sourceVariant,
  systemEntryLabel,
  systemEntryVariant,
} from "@/modules/environment/environmentPresentation";
import { useEnvironmentProfile } from "@/modules/environment/hooks/useEnvironmentProfile";

type CuratedLane = "all" | "paths" | "runtime";

const LANES: Array<{ key: CuratedLane; label: string }> = [
  { key: "all", label: "All" },
  { key: "paths", label: "Filesystem" },
  { key: "runtime", label: "Runtime" },
];

export function BuiltInScope({ scope }: { scope: EnvScope }) {
  const queryClient = useQueryClient();
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
      ? envQuery.data.entries.filter(
          (entry) => profile.enabled[entry.name] ?? (profile.draft[entry.name] ?? "").trim() !== "",
        ).length
      : countActive(envQuery.data.entries, (entry) => entry.value_redacted);
  const rows: EnvTableRow[] = visibleEntries.map((entry) =>
    scope === "curated" ? curatedRow(entry, profile) : systemRow(entry),
  );

  return (
    <>
      <div className="env-intro">
        <span className="env-intro__text">
          {scope === "curated"
            ? "Curated variables are read from the system environment; toggles clear or restore a value before you apply it."
            : "System-inherited values are shown read-only; use search to filter by name or description."}
        </span>
        <span className="env-intro__summary">
          {scope === "curated"
            ? `${enabledCount} set / ${envQuery.data.count} total`
            : `${envQuery.data.count} inherited`}
        </span>
        <RefreshButton
          label="environment"
          onRefresh={() => void envQuery.refetch()}
          isFetching={envQuery.isFetching}
        />
      </div>

      <EnvScopeSwitcher
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

      <ConfirmDialog action={applyAction} actionTitle="Apply environment values" />
    </>
  );
}

function curatedRow(
  entry: EnvEntry,
  profile: ReturnType<typeof useEnvironmentProfile>,
): EnvTableRow {
  const value = profile.draft[entry.name] ?? "";
  const dirty = entry.name in profile.dirtyValues;
  const isOn = profile.enabled[entry.name] ?? value.trim() !== "";
  return {
    entry,
    value,
    isOn,
    canToggle: entry.editable,
    editing: entry.editable && isOn,
    dirty,
    isSecret: isSensitiveEnvironmentEntry(entry),
    stateVariant: dirty ? "update" : sourceVariant(entry.source),
    stateLabel: dirty ? "staged" : sourceLabel(entry.source),
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
    isSecret: isSensitiveEnvironmentEntry(entry),
    stateVariant: systemEntryVariant(entry),
    stateLabel: systemEntryLabel(entry),
  };
}
