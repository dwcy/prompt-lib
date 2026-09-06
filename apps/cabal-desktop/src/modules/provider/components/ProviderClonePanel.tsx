// Clone runway card: selected repo -> destination -> clone+switch steps, restyled to sit beside
// ProviderRepoListCard in place of the mock's "open pull requests" panel (no PR data available).
import type { ProviderRepo } from "@/api/projectLifecycle";
import { JobPane } from "@/components/JobPane";
import type { ActionPhase } from "@/hooks/useAction";

export interface ProviderClonePanelProps {
  selectedRepo: ProviderRepo | null;
  destination: string;
  onDestinationChange: (value: string) => void;
  onClone: () => void;
  clonePhase: ActionPhase;
  cloneJobId: string | null;
}

export function ProviderClonePanel({
  selectedRepo,
  destination,
  onDestinationChange,
  onClone,
  clonePhase,
  cloneJobId,
}: ProviderClonePanelProps) {
  const destinationReady = destination.trim().length > 0;
  const cloneBusy = clonePhase === "preparing" || clonePhase === "executing";

  return (
    <section className="provider-clone-panel">
      <header className="provider-clone-panel__header">
        <strong className="select-none">Clone runway</strong>
        <span className="provider-clone-panel__target">
          {selectedRepo?.full_name ?? "Select a repository"}
        </span>
      </header>
      <ol className="provider-clone-panel__runway" aria-label="Clone and switch workflow">
        <li className={selectedRepo === null ? "" : "is-ready"}>
          <span>01</span>
          <div>
            <small>Source</small>
            <strong>{selectedRepo?.full_name ?? "Select a repository"}</strong>
            <p>{selectedRepo?.url ?? "Repository metadata will appear here."}</p>
          </div>
        </li>
        <li className={destinationReady ? "is-ready" : ""}>
          <span>02</span>
          <label className="provider-clone-panel__field">
            <small>Destination</small>
            <input
              type="text"
              value={destination}
              onChange={(event) => onDestinationChange(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              placeholder="C:\\projects\\repo"
            />
          </label>
        </li>
        <li className={selectedRepo !== null && destinationReady ? "is-ready" : ""}>
          <span>03</span>
          <div>
            <small>Workspace handoff</small>
            <strong>Clone, register, and switch context</strong>
            <p>The new checkout becomes the active Cabal project after the job succeeds.</p>
          </div>
        </li>
      </ol>
      <button
        type="button"
        className="provider-clone-panel__action"
        onClick={onClone}
        disabled={selectedRepo === null || !destinationReady || cloneBusy}
      >
        {clonePhase === "preparing"
          ? "Preparing clone…"
          : clonePhase === "executing"
            ? "Starting clone…"
            : "Clone and switch workspace"}
      </button>
      {cloneJobId !== null ? <JobPane jobId={cloneJobId} /> : null}
    </section>
  );
}
