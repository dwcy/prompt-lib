import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { type LocalConfigAction, useLocalConfig } from "@/api/config";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import { useProjectContextStore } from "@/stores/projectContext";

type SelectionState = Record<string, Set<string>>;

export function LocalConfigModule() {
  const queryClient = useQueryClient();
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  const [template, setTemplate] = useState<string | null>(null);
  const [gitignore, setGitignore] = useState<string | null>(null);
  const [selection, setSelection] = useState<SelectionState>({});
  const [pendingTitle, setPendingTitle] = useState("Apply local config");
  const localConfigQuery = useLocalConfig(template, gitignore);
  const action = useAction("local_config.apply_group");

  useEffect(() => {
    if (action.phase !== "succeeded") return;
    setSelection({});
    void queryClient.invalidateQueries({ queryKey: queryKeys.scoped("localConfig", projectPath) });
  }, [action.phase, queryClient, projectPath]);

  if (localConfigQuery.isPending) return <EmptyState title="Loading local config plan..." />;
  if (localConfigQuery.isError) {
    return (
      <EmptyState title="Could not load local config plan" body={localConfigQuery.error.message} />
    );
  }

  const planSummary = summarizePlan(localConfigQuery.data.actions, selection);

  return (
    <div className="us3-module">
      <header className="us3-module__header">
        <div>
          <h1>Local Project Config</h1>
          <p>Preview and apply project-scoped scaffolding groups with per-item control.</p>
        </div>
        <div className="us3-toolbar">
          <label className="us3-field">
            Template
            <select
              value={template ?? ""}
              onChange={(event) => {
                setTemplate(event.currentTarget.value || null);
                setSelection({});
              }}
            >
              <option value="">None</option>
              {localConfigQuery.data.template_options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="us3-field">
            Gitignore
            <select
              value={gitignore ?? ""}
              onChange={(event) => {
                setGitignore(event.currentTarget.value || null);
                setSelection({});
              }}
            >
              <option value="">None</option>
              {(localConfigQuery.data.gitignore_options ?? []).map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <section className="local-blueprint-summary">
        <div>
          <span className="us3-eyebrow">Scaffold blueprint</span>
          <strong>{planSummary.selected} file operations staged</strong>
          <p>
            {planSummary.ready} groups ready, {planSummary.complete} already satisfied.
          </p>
        </div>
        <div className="local-blueprint-summary__metrics">
          <BlueprintMetric label="new" value={planSummary.newCount} tone="new" />
          <BlueprintMetric label="changed" value={planSummary.changedCount} tone="changed" />
          <BlueprintMetric label="stable" value={planSummary.skipCount} tone="stable" />
        </div>
      </section>

      {localConfigQuery.data.actions.length === 0 ? (
        <EmptyState title="No local config actions available" />
      ) : (
        <div className="local-config-blueprint">
          {localConfigQuery.data.actions.map((item, index) => (
            <LocalConfigCard
              key={item.key}
              step={index + 1}
              action={item}
              selectedKeys={selectedKeysFor(item, selection)}
              onToggle={(itemKey, checked) =>
                setSelection((current) => updateSelection(current, item, itemKey, checked))
              }
              onApply={() => {
                const itemKeys = Array.from(selectedKeysFor(item, selection));
                setPendingTitle(`Apply ${item.label}`);
                action.prepare({ action: item.key, item_keys: itemKeys, template, gitignore });
              }}
            />
          ))}
        </div>
      )}

      <ConfirmDialog
        isOpen={action.phase !== "idle" && action.phase !== "succeeded"}
        actionTitle={pendingTitle}
        ticket={action.ticket}
        phase={action.phase}
        reviewNotice={action.reviewNotice}
        error={action.error}
        onConfirm={action.confirm}
        onCancel={action.reset}
      />

      {action.jobId !== null ? <JobPane jobId={action.jobId} /> : null}
    </div>
  );
}

function LocalConfigCard({
  step,
  action,
  selectedKeys,
  onToggle,
  onApply,
}: {
  step: number;
  action: LocalConfigAction;
  selectedKeys: Set<string>;
  onToggle: (itemKey: string, checked: boolean) => void;
  onApply: () => void;
}) {
  const counts = countPreviewItems(action);

  return (
    <article className="local-config-stage">
      <span className="local-config-stage__number">{String(step).padStart(2, "0")}</span>
      <div className="local-config-stage__body">
        <header className="local-config-card__header">
          <div>
            <h2>{action.label}</h2>
            <p>
              {counts.newCount} new · {counts.changedCount} changed · {counts.skipCount} already set
            </p>
          </div>
          <StatePill variant={action.applicable ? "update" : "ok"} label={action.applied_state} />
        </header>
        <ul className="local-config-card__items">
          {action.preview_items.map((item) => (
            <li key={item.key}>
              <label className="local-config-card__item">
                <input
                  type="checkbox"
                  checked={selectedKeys.has(item.key)}
                  disabled={item.state === "skip"}
                  onChange={(event) => onToggle(item.key, event.currentTarget.checked)}
                />
                <span>{item.rel_path}</span>
                <StatePill
                  variant={
                    item.state === "changed" ? "update" : item.state === "new" ? "open" : "ok"
                  }
                  label={item.state}
                />
              </label>
            </li>
          ))}
        </ul>
        <button type="button" onClick={onApply} disabled={selectedKeys.size === 0}>
          Review {selectedKeys.size}
        </button>
      </div>
    </article>
  );
}

function BlueprintMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "new" | "changed" | "stable";
}) {
  return (
    <span className={`local-blueprint-metric local-blueprint-metric--${tone}`}>
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

function summarizePlan(actions: LocalConfigAction[], selection: SelectionState) {
  const previews = actions.flatMap((item) => item.preview_items);
  return {
    selected: actions.reduce((total, item) => total + selectedKeysFor(item, selection).size, 0),
    ready: actions.filter((item) => item.applicable).length,
    complete: actions.filter((item) => !item.applicable).length,
    newCount: previews.filter((item) => item.state === "new").length,
    changedCount: previews.filter((item) => item.state === "changed").length,
    skipCount: previews.filter((item) => item.state === "skip").length,
  };
}

function selectedKeysFor(action: LocalConfigAction, selection: SelectionState): Set<string> {
  const override = selection[action.key];
  if (override !== undefined) return override;
  return new Set(action.preview_items.filter((item) => item.selected).map((item) => item.key));
}

function updateSelection(
  current: SelectionState,
  action: LocalConfigAction,
  itemKey: string,
  checked: boolean,
): SelectionState {
  const next = { ...current };
  const selected = new Set(selectedKeysFor(action, current));
  if (checked) selected.add(itemKey);
  else selected.delete(itemKey);
  next[action.key] = selected;
  return next;
}

function countPreviewItems(action: LocalConfigAction) {
  return {
    newCount: action.preview_items.filter((item) => item.state === "new").length,
    changedCount: action.preview_items.filter((item) => item.state === "changed").length,
    skipCount: action.preview_items.filter((item) => item.state === "skip").length,
  };
}
