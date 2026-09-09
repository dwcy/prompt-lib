import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { type ConfigFile, type ConfigTarget, useConfigDiff, useConfigTree } from "@/api/config";
import { queryKeys } from "@/api/queryKeys";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DiffView } from "@/components/DiffView";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { RefreshButton } from "@/components/RefreshButton";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import { DeployComponentTree } from "./DeployComponentTree";
import { ALL_GROUPS, DeployGroupFilter } from "./DeployGroupFilter";
import { fileStateVariant } from "./deployPresentation";
import { FileViewDialog } from "./FileViewDialog";

export interface DeployTreePanelProps {
  target: ConfigTarget;
  actionId: "config.apply" | "codex.apply";
}

export function DeployTreePanel({ target, actionId }: DeployTreePanelProps) {
  const queryClient = useQueryClient();
  const treeQuery = useConfigTree(target);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set());
  const [diffPath, setDiffPath] = useState<string | null>(null);
  const [group, setGroup] = useState<string>(ALL_GROUPS);
  const [viewFile, setViewFile] = useState<ConfigFile | null>(null);
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
  const visibleComponents =
    group === ALL_GROUPS
      ? treeQuery.data.components
      : treeQuery.data.components.filter((component) => component.group === group);
  // "Select drift" queues what is on screen — queueing hidden groups from behind a filter
  // would put files into the write that the user never saw.
  const visibleActionableFiles = visibleComponents.flatMap((component) =>
    component.files.filter((file) => file.state !== "unchanged"),
  );
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
    <div className="cfg-deploy__panel">
      <section className="cfg-deploy__metrics">
        <Metric label="Changed" value={treeQuery.data.drift.changed_count} tone="update" />
        <Metric label="New" value={treeQuery.data.drift.new_count} tone="open" />
        <Metric label="Extras" value={treeQuery.data.drift.extras_count} tone="stale" />
        <Metric label="Stable" value={treeQuery.data.drift.unchanged_count} tone="ok" />
        <CardRefreshFooter>
          <RefreshButton
            label="deploy tree"
            onRefresh={() => void treeQuery.refetch()}
            isFetching={treeQuery.isFetching}
          />
        </CardRefreshFooter>
      </section>

      <section className="cfg-deploy__command-strip">
        <div className="cfg-deploy__command-summary">
          <span className="cfg-deploy__eyebrow">Deploy queue</span>
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
        <ol className="cfg-deploy__steps" aria-label="Deploy workflow">
          <li
            className={
              diffPath === null ? "cfg-deploy__step" : "cfg-deploy__step cfg-deploy__step--done"
            }
          >
            Review diff
          </li>
          <li
            className={
              selectedCount === 0 ? "cfg-deploy__step" : "cfg-deploy__step cfg-deploy__step--done"
            }
          >
            Build queue
          </li>
          <li className="cfg-deploy__step">Confirm write</li>
        </ol>
        <div className="cfg-deploy__toolbar">
          <button
            type="button"
            className="cfg-deploy__toolbar-btn"
            onClick={() =>
              setSelectedPaths(new Set(visibleActionableFiles.map((file) => file.rel_path)))
            }
            disabled={visibleActionableFiles.length === 0}
          >
            Select drift
          </button>
          <button
            type="button"
            className="cfg-deploy__toolbar-btn"
            onClick={() => setSelectedPaths(new Set())}
            disabled={selectedCount === 0}
          >
            Clear
          </button>
          <button
            type="button"
            className="cfg-deploy__toolbar-btn cfg-deploy__toolbar-btn--primary"
            onClick={() => action.prepare(actionParams)}
            disabled={selectedCount === 0}
          >
            Apply {selectedCount}
          </button>
        </div>
      </section>

      <DeployGroupFilter
        components={treeQuery.data.components}
        active={group}
        onChange={setGroup}
      />

      <div className="cfg-deploy__body">
        <DeployComponentTree
          components={visibleComponents}
          selectedPaths={selectedPaths}
          onToggleFile={(relPath, checked) =>
            setSelectedPaths((current) => updatePathSelection(current, relPath, checked))
          }
          onToggleComponent={(files, checked) =>
            setSelectedPaths((current) => updateComponentSelection(current, files, checked))
          }
          onShowDiff={setDiffPath}
          onViewFile={setViewFile}
        />

        <aside className="cfg-deploy__diff">
          <header className="cfg-deploy__diff-header">
            <div>
              <h2>Diff Review</h2>
              {diffPath !== null ? <p className="cfg-deploy__diff-path">{diffPath}</p> : null}
            </div>
            {diffFile !== null ? (
              <StatePill variant={fileStateVariant(diffFile.state)} label={diffFile.state} />
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
          {diffPath !== null ? (
            <CardRefreshFooter>
              <RefreshButton
                label="diff"
                onRefresh={() => void diffQuery.refetch()}
                isFetching={diffQuery.isFetching}
              />
            </CardRefreshFooter>
          ) : null}
        </aside>
      </div>

      {viewFile !== null ? (
        <FileViewDialog target={target} file={viewFile} onClose={() => setViewFile(null)} />
      ) : null}

      <ConfirmDialog action={action} actionTitle={`Apply ${target} config`} />

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
    <div className={`cfg-deploy__metric cfg-deploy__metric--${tone}`}>
      <span className="cfg-deploy__metric-label">{label}</span>
      <strong className="cfg-deploy__metric-value">{value}</strong>
    </div>
  );
}
