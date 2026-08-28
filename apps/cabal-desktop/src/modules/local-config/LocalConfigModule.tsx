// Local Project Config console module: template/gitignore selects, blueprint summary strip, and
// per-group action cards with per-item preview toggles and confirmed apply flow.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useLocalConfig } from "@/api/config";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { useAction } from "@/hooks/useAction";
import { BlueprintMetric, LocalConfigCard } from "@/modules/local-config/LocalConfigCard";
import type { SelectionState } from "@/modules/local-config/localConfigSelection";
import {
  selectedKeysFor,
  summarizePlan,
  updateSelection,
} from "@/modules/local-config/localConfigSelection";
import { useProjectContextStore } from "@/stores/projectContext";
import "./LocalConfigModule.css";

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
    <div className="lcfg">
      <header className="lcfg__header">
        <div>
          <h1>Local Project Config</h1>
          <p>Preview and apply project-scoped scaffolding groups with per-item control.</p>
        </div>
        <div className="lcfg__toolbar">
          <label className="lcfg__field">
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
          <label className="lcfg__field">
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

      <section className="lcfg__summary">
        <div>
          <span className="lcfg__eyebrow">Scaffold blueprint</span>
          <strong>{planSummary.selected} file operations staged</strong>
          <p>
            {planSummary.ready} groups ready, {planSummary.complete} already satisfied.
          </p>
        </div>
        <div className="lcfg__summary-metrics">
          <BlueprintMetric label="new" value={planSummary.newCount} tone="new" />
          <BlueprintMetric label="changed" value={planSummary.changedCount} tone="changed" />
          <BlueprintMetric label="stable" value={planSummary.skipCount} tone="stable" />
        </div>
      </section>

      {localConfigQuery.data.actions.length === 0 ? (
        <EmptyState title="No local config actions available" />
      ) : (
        <div className="lcfg__list">
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

      <ConfirmDialog action={action} actionTitle={pendingTitle} />

      {action.jobId !== null ? <JobPane jobId={action.jobId} /> : null}
    </div>
  );
}
