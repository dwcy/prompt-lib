import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { type SettingEntry, useSettings } from "@/api/config";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import { useProjectContextStore } from "@/stores/projectContext";
import "./SettingsModule.css";

type SourceFilter = "all" | SettingEntry["source"];

export function SettingsModule() {
  const queryClient = useQueryClient();
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  const settingsQuery = useSettings();
  const toggleAction = useAction("settings.toggle");
  const resetAction = useAction("settings.reset_local");
  const [pendingLabel, setPendingLabel] = useState("Change setting");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [search, setSearch] = useState("");

  const groupedEntries = useMemo(
    () => ({
      overrides:
        settingsQuery.data?.entries.filter((entry) => entry.source === "local_override") ?? [],
      inherited: settingsQuery.data?.entries.filter((entry) => entry.source === "global") ?? [],
      defaults: settingsQuery.data?.entries.filter((entry) => entry.source === "unset") ?? [],
    }),
    [settingsQuery.data],
  );

  const visibleEntries = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (settingsQuery.data?.entries ?? []).filter(
      (entry) =>
        (sourceFilter === "all" || entry.source === sourceFilter) &&
        (needle.length === 0 ||
          entry.label.toLowerCase().includes(needle) ||
          entry.key.toLowerCase().includes(needle) ||
          entry.description.toLowerCase().includes(needle)),
    );
  }, [search, settingsQuery.data, sourceFilter]);

  useEffect(() => {
    if (toggleAction.phase !== "succeeded" && resetAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.scoped("settings", projectPath) });
  }, [toggleAction.phase, resetAction.phase, queryClient, projectPath]);

  if (settingsQuery.isPending) return <EmptyState title="Loading settings catalog..." />;
  if (settingsQuery.isError) {
    return <EmptyState title="Could not load settings" body={settingsQuery.error.message} />;
  }

  return (
    <div className="settings-console">
      <section className="settings-command-center">
        <div className="settings-command-center__intro">
          <span className="settings-eyebrow select-none">Resolution map</span>
          <h1>Settings</h1>
          <p>
            Trace each value from its upstream origin through the project layer to the effective
            runtime state.
          </p>
        </div>
        <div className="settings-command-panel">
          <ol className="settings-inheritance-flow" aria-label="Settings resolution order">
            <li className="is-active">
              <span className="settings-inheritance-flow__step">01</span>
              <strong className="settings-inheritance-flow__label">Origin</strong>
              <small className="settings-inheritance-flow__detail">global or catalog</small>
            </li>
            <li className={groupedEntries.overrides.length > 0 ? "is-active" : ""}>
              <span className="settings-inheritance-flow__step">02</span>
              <strong className="settings-inheritance-flow__label">Project layer</strong>
              <small className="settings-inheritance-flow__detail">
                {groupedEntries.overrides.length} override(s)
              </small>
            </li>
            <li className="is-effective">
              <span className="settings-inheritance-flow__step">03</span>
              <strong className="settings-inheritance-flow__label">Effective value</strong>
              <small className="settings-inheritance-flow__detail">runtime result</small>
            </li>
          </ol>
          <button
            type="button"
            onClick={() => {
              setPendingLabel("Reset local overrides");
              resetAction.prepare({});
            }}
            disabled={!settingsQuery.data.project_selected || groupedEntries.overrides.length === 0}
          >
            Reset local overrides
          </button>
        </div>
      </section>

      <section className="settings-resolution-toolbar">
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Find a setting or key"
          aria-label="Find a setting"
        />
        <fieldset className="settings-source-filter">
          <legend className="settings-vh">Setting provenance</legend>
          <SourceButton
            label="All"
            count={settingsQuery.data.entries.length}
            active={sourceFilter === "all"}
            onClick={() => setSourceFilter("all")}
          />
          <SourceButton
            label="Project"
            count={groupedEntries.overrides.length}
            active={sourceFilter === "local_override"}
            onClick={() => setSourceFilter("local_override")}
          />
          <SourceButton
            label="Global"
            count={groupedEntries.inherited.length}
            active={sourceFilter === "global"}
            onClick={() => setSourceFilter("global")}
          />
          <SourceButton
            label="Defaults"
            count={groupedEntries.defaults.length}
            active={sourceFilter === "unset"}
            onClick={() => setSourceFilter("unset")}
          />
        </fieldset>
        <span className="settings-resolution-toolbar__count">{visibleEntries.length} visible</span>
      </section>

      <section className="settings-resolution-map">
        <header>
          <span>Setting</span>
          <span>Resolution path</span>
          <span>Command</span>
        </header>
        {visibleEntries.length === 0 ? (
          <EmptyState title="No settings matched" />
        ) : (
          visibleEntries.map((entry, index) => (
            <SettingResolutionRow
              key={entry.key}
              entry={entry}
              index={index}
              projectSelected={settingsQuery.data.project_selected}
              onToggle={() => {
                const nextValue = !entry.value_state;
                setPendingLabel((nextValue ? "Enable " : "Disable ") + entry.label);
                toggleAction.prepare({ key: entry.key, value: nextValue });
              }}
            />
          ))
        )}
      </section>

      <ConfirmDialog
        isOpen={toggleAction.phase !== "idle" && toggleAction.phase !== "succeeded"}
        actionTitle={pendingLabel}
        ticket={toggleAction.ticket}
        phase={toggleAction.phase}
        reviewNotice={toggleAction.reviewNotice}
        error={toggleAction.error}
        onConfirm={toggleAction.confirm}
        onCancel={toggleAction.reset}
      />
      <ConfirmDialog
        isOpen={resetAction.phase !== "idle" && resetAction.phase !== "succeeded"}
        actionTitle="Reset local overrides"
        ticket={resetAction.ticket}
        phase={resetAction.phase}
        reviewNotice={resetAction.reviewNotice}
        error={resetAction.error}
        onConfirm={resetAction.confirm}
        onCancel={resetAction.reset}
      />
    </div>
  );
}

function SourceButton({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" className={active ? "is-active" : ""} onClick={onClick}>
      <span>{label}</span>
      <strong>{count}</strong>
    </button>
  );
}

function SettingResolutionRow({
  entry,
  index,
  projectSelected,
  onToggle,
}: {
  entry: SettingEntry;
  index: number;
  projectSelected: boolean;
  onToggle: () => void;
}) {
  const origin =
    entry.source === "unset"
      ? { label: "Catalog default", detail: "built in" }
      : entry.source === "global"
        ? { label: "Global settings", detail: "inherited" }
        : { label: "Global baseline", detail: "upstream" };
  const projectLayer =
    entry.source === "local_override"
      ? { label: "Local override", detail: "active", active: true }
      : { label: "Pass-through", detail: "no override", active: false };

  return (
    <article className="settings-resolution-row">
      <span className="settings-resolution-row__index">{String(index + 1).padStart(2, "0")}</span>
      <div className="settings-resolution-row__identity">
        <span>
          <h2>{entry.label}</h2>
          <StatePill
            variant={
              entry.source === "local_override"
                ? "update"
                : entry.source === "global"
                  ? "ok"
                  : "unavailable"
            }
            label={entry.source.replace("_", " ")}
          />
        </span>
        <p>{entry.description}</p>
        <code>{entry.key}</code>
      </div>
      <div className="settings-resolution-row__trace">
        <ResolutionNode label={origin.label} detail={origin.detail} />
        <i aria-hidden="true">&gt;</i>
        <ResolutionNode
          label={projectLayer.label}
          detail={projectLayer.detail}
          active={projectLayer.active}
        />
        <i aria-hidden="true">&gt;</i>
        <ResolutionNode label={entry.value_state ? "On" : "Off"} detail="effective" active />
      </div>
      <div className="settings-resolution-row__command">
        <small>{entry.target_file}</small>
        <button
          type="button"
          role="switch"
          aria-checked={entry.value_state}
          aria-label={`${entry.value_state ? "Disable" : "Enable"} ${entry.label}`}
          className={`settings-toggle${entry.value_state ? " is-on" : ""}`}
          onClick={onToggle}
          disabled={!projectSelected}
        >
          <span className="settings-toggle__knob" />
        </button>
      </div>
    </article>
  );
}

function ResolutionNode({
  label,
  detail,
  active = false,
}: {
  label: string;
  detail: string;
  active?: boolean;
}) {
  return (
    <span className={active ? "is-active" : undefined}>
      <small className="settings-resolution-row__trace-detail">{detail}</small>
      <strong className="settings-resolution-row__trace-label">{label}</strong>
    </span>
  );
}
