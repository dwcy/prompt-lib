// Deploy panel for one target: drift metrics, the deploy queue, the group filter and the config
// tree. Owns the selection and which file is open in the reader; the pieces render themselves.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { type ConfigFile, type ConfigTarget, useConfigTree } from "@/api/config";
import { queryKeys } from "@/api/queryKeys";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { RefreshButton } from "@/components/RefreshButton";
import { useAction } from "@/hooks/useAction";
import { DeployCommandStrip } from "./DeployCommandStrip";
import { DeployComponentTree } from "./DeployComponentTree";
import { ALL_GROUPS, DeployGroupFilter } from "./DeployGroupFilter";
import { FileViewDialog } from "./FileViewDialog";
import type { FileViewTab } from "./fileViewTabs";

export interface DeployTreePanelProps {
  target: ConfigTarget;
  actionId: "config.apply" | "codex.apply";
}

export function DeployTreePanel({ target, actionId }: DeployTreePanelProps) {
  const queryClient = useQueryClient();
  const treeQuery = useConfigTree(target);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set());
  const [group, setGroup] = useState<string>(ALL_GROUPS);
  const [viewFile, setViewFile] = useState<ConfigFile | null>(null);
  const [viewTab, setViewTab] = useState<FileViewTab | undefined>(undefined);
  // Only drives the "Review diff" step: it stays done once a diff has actually been opened.
  const [diffReviewed, setDiffReviewed] = useState(false);
  const action = useAction(actionId);

  function openFile(file: ConfigFile, tab?: FileViewTab): void {
    setViewFile(file);
    setViewTab(tab);
    if (tab === "diff") setDiffReviewed(true);
  }

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

      <DeployCommandStrip
        selectedPaths={Array.from(selectedPaths)}
        driftCount={driftCount}
        diffReviewed={diffReviewed}
        selectableCount={visibleActionableFiles.length}
        onSelectDrift={() =>
          setSelectedPaths(new Set(visibleActionableFiles.map((file) => file.rel_path)))
        }
        onClear={() => setSelectedPaths(new Set())}
        onApply={() => action.prepare(actionParams)}
      />

      <DeployGroupFilter
        components={treeQuery.data.components}
        active={group}
        onChange={setGroup}
      />

      <DeployComponentTree
        components={visibleComponents}
        selectedPaths={selectedPaths}
        onToggleFile={(relPath, checked) =>
          setSelectedPaths((current) => updatePathSelection(current, relPath, checked))
        }
        onToggleComponent={(files, checked) =>
          setSelectedPaths((current) => updateComponentSelection(current, files, checked))
        }
        onShowDiff={(file) => openFile(file, "diff")}
        onViewFile={(file) => openFile(file)}
      />

      {viewFile !== null ? (
        <FileViewDialog
          target={target}
          file={viewFile}
          initialView={viewTab}
          onClose={() => setViewFile(null)}
        />
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
