import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { type ConfigFile, type ConfigTarget, useConfigDiff, useConfigTree } from "@/api/config";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DiffView } from "@/components/DiffView";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";

export interface DeployTreePanelProps {
  target: ConfigTarget;
  actionId: "config.apply" | "codex.apply";
}

export function DeployTreePanel({ target, actionId }: DeployTreePanelProps) {
  const queryClient = useQueryClient();
  const treeQuery = useConfigTree(target);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set());
  const [diffPath, setDiffPath] = useState<string | null>(null);
  const diffQuery = useConfigDiff(target, diffPath);
  const action = useAction(actionId);

  const actionableFiles = useMemo(
    () =>
      treeQuery.data?.components.flatMap((component) =>
        component.files.filter((file) => file.state !== "unchanged"),
      ) ?? [],
    [treeQuery.data],
  );
  const selectedFiles = useMemo(
    () => actionableFiles.filter((file) => selectedPaths.has(file.rel_path)),
    [actionableFiles, selectedPaths],
  );

  useEffect(() => {
    if (action.phase !== "succeeded") return;
    setSelectedPaths(new Set());
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("config", "tree", target) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("config", "diff", target) });
  }, [action.phase, queryClient, target]);

  if (treeQuery.isPending) return <EmptyState title="Loading deployment tree..." />;
  if (treeQuery.isError) {
    return <EmptyState title="Could not load deployment tree" body={treeQuery.error.message} />;
  }

  const selectedCount = selectedPaths.size;
  const driftCount = treeQuery.data.drift.changed_count + treeQuery.data.drift.new_count;
  const diffFile =
    diffPath === null
      ? null
      : (treeQuery.data.components
          .flatMap((component) => component.files)
          .find((file) => file.rel_path === diffPath) ?? null);
  const actionParams =
    actionId === "config.apply"
      ? { target, paths: Array.from(selectedPaths) }
      : { paths: Array.from(selectedPaths) };

  return (
    <div className="deploy-tree-panel">
      <section className="us3-summary-grid">
        <Metric label="Changed" value={treeQuery.data.drift.changed_count} tone="update" />
        <Metric label="New" value={treeQuery.data.drift.new_count} tone="open" />
        <Metric label="Extras" value={treeQuery.data.drift.extras_count} tone="stale" />
        <Metric label="Stable" value={treeQuery.data.drift.unchanged_count} tone="ok" />
      </section>

      <section className="deploy-command-strip">
        <div className="deploy-command-strip__summary">
          <span className="us3-eyebrow">Deploy queue</span>
          <strong>
            {selectedCount === 0 ? "Nothing selected" : `${selectedCount} file(s) ready`}
          </strong>
          <p>
            {selectedCount === 0
              ? `${driftCount} drifted file(s) are available for review.`
              : selectedFiles
                  .slice(0, 3)
                  .map((file) => file.rel_path)
                  .join(", ")}
          </p>
        </div>
        <ol className="deploy-command-strip__steps" aria-label="Deploy workflow">
          <li className={diffPath === null ? "" : "deploy-command-strip__step--done"}>
            Review diff
          </li>
          <li className={selectedCount === 0 ? "" : "deploy-command-strip__step--done"}>
            Build queue
          </li>
          <li>Confirm write</li>
        </ol>
        <div className="us3-toolbar">
          <button
            type="button"
            onClick={() => setSelectedPaths(new Set(actionableFiles.map((file) => file.rel_path)))}
          >
            Select drift
          </button>
          <button
            type="button"
            onClick={() => setSelectedPaths(new Set())}
            disabled={selectedCount === 0}
          >
            Clear
          </button>
          <button
            type="button"
            onClick={() => action.prepare(actionParams)}
            disabled={selectedCount === 0}
          >
            Apply {selectedCount}
          </button>
        </div>
      </section>

      <div className="deploy-tree-panel__body">
        <section className="deploy-tree">
          {treeQuery.data.components.map((component) => {
            const files = component.files;
            const selectedInComponent = files.filter((file) =>
              selectedPaths.has(file.rel_path),
            ).length;
            const changedInComponent = files.filter((file) => file.state === "changed").length;
            const newInComponent = files.filter((file) => file.state === "new").length;
            const checked = files.length > 0 && selectedInComponent === files.length;
            const indeterminate = selectedInComponent > 0 && selectedInComponent < files.length;

            return (
              <article key={component.key} className="deploy-component">
                <label className="deploy-component__header">
                  <input
                    type="checkbox"
                    checked={checked}
                    ref={(node) => {
                      if (node !== null) node.indeterminate = indeterminate;
                    }}
                    onChange={(event) =>
                      setSelectedPaths((current) =>
                        updateComponentSelection(current, files, event.currentTarget.checked),
                      )
                    }
                  />
                  <span className="deploy-component__title-block">
                    <span className="deploy-component__title">{component.label}</span>
                    <span className="deploy-component__group">{component.group}</span>
                  </span>
                  <span className="deploy-component__rollup">
                    {changedInComponent} changed · {newInComponent} new · {selectedInComponent}{" "}
                    queued
                  </span>
                </label>

                <ul className="deploy-file-list">
                  {files.map((file) => (
                    <li key={file.rel_path} className="deploy-file-list__item">
                      <label className="deploy-file-list__select">
                        <input
                          type="checkbox"
                          checked={selectedPaths.has(file.rel_path)}
                          disabled={file.state === "unchanged"}
                          onChange={(event) =>
                            setSelectedPaths((current) =>
                              updatePathSelection(
                                current,
                                file.rel_path,
                                event.currentTarget.checked,
                              ),
                            )
                          }
                        />
                        <span className="deploy-file-list__path">{file.rel_path}</span>
                      </label>
                      <StatePill
                        variant={
                          file.state === "changed" ? "update" : file.state === "new" ? "open" : "ok"
                        }
                        label={file.state}
                      />
                      <button
                        type="button"
                        onClick={() => setDiffPath(file.rel_path)}
                        disabled={!file.diff_available}
                      >
                        Diff
                      </button>
                    </li>
                  ))}
                </ul>
              </article>
            );
          })}
        </section>

        <aside className="deploy-diff-panel">
          <header className="deploy-diff-panel__header">
            <div>
              <h2>Diff Review</h2>
              {diffPath !== null ? <p className="deploy-diff-panel__path">{diffPath}</p> : null}
            </div>
            {diffFile !== null ? (
              <StatePill
                variant={
                  diffFile.state === "changed" ? "update" : diffFile.state === "new" ? "open" : "ok"
                }
                label={diffFile.state}
              />
            ) : null}
          </header>
          {diffPath === null ? (
            <EmptyState title="Select a changed or new file to inspect its exact write." />
          ) : diffQuery.isPending ? (
            <EmptyState title="Loading diff..." />
          ) : diffQuery.isError ? (
            <EmptyState title="Could not load diff" body={diffQuery.error.message} />
          ) : (
            <DiffView diffText={diffQuery.data.diff_text} />
          )}
        </aside>
      </div>

      <ConfirmDialog
        isOpen={action.phase !== "idle" && action.phase !== "succeeded"}
        actionTitle={`Apply ${target} config`}
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

function updatePathSelection(current: Set<string>, path: string, checked: boolean): Set<string> {
  const next = new Set(current);
  if (checked) next.add(path);
  else next.delete(path);
  return next;
}

function updateComponentSelection(
  current: Set<string>,
  files: ConfigFile[],
  checked: boolean,
): Set<string> {
  const next = new Set(current);
  for (const file of files) {
    if (file.state === "unchanged") continue;
    if (checked) next.add(file.rel_path);
    else next.delete(file.rel_path);
  }
  return next;
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "ok" | "open" | "stale" | "update";
}) {
  return (
    <div className={`us3-metric us3-metric--${tone}`}>
      <span className="us3-metric__label">{label}</span>
      <strong className="us3-metric__value">{value}</strong>
    </div>
  );
}
