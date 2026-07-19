import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { type BackupSet, useConfigBackups, useConfigExtras } from "@/api/config";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";

export function CleanupRestoreModule() {
  const queryClient = useQueryClient();
  const extrasQuery = useConfigExtras("claude");
  const cleanupBackups = useConfigBackups("cleanup");
  const settingsBackups = useConfigBackups("settings");
  const cleanupAction = useAction("config.cleanup");
  const restoreCleanupAction = useAction("config.restore_cleanup");
  const restoreSettingsAction = useAction("config.restore_settings");
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set());
  const [selectionTouched, setSelectionTouched] = useState(false);

  const allExtras = useMemo(
    () => extrasQuery.data?.groups.flatMap((group) => group.extras) ?? [],
    [extrasQuery.data],
  );
  const staleExtras = useMemo(
    () => allExtras.filter((extra) => extra.classification === "stale"),
    [allExtras],
  );
  const unknownExtras = allExtras.length - staleExtras.length;
  const backupTimeline = useMemo(
    () =>
      [...(cleanupBackups.data?.backups ?? []), ...(settingsBackups.data?.backups ?? [])].sort(
        (left, right) => right.created_at.localeCompare(left.created_at),
      ),
    [cleanupBackups.data, settingsBackups.data],
  );

  useEffect(() => {
    if (selectionTouched || allExtras.length === 0) return;
    setSelectedPaths(new Set(staleExtras.map((extra) => extra.rel_path)));
  }, [allExtras.length, staleExtras, selectionTouched]);

  useEffect(() => {
    if (cleanupAction.phase === "succeeded") {
      setSelectedPaths(new Set());
      setSelectionTouched(false);
    }
    const phase =
      cleanupAction.phase === "succeeded" ||
      restoreCleanupAction.phase === "succeeded" ||
      restoreSettingsAction.phase === "succeeded";
    if (!phase) return;
    void queryClient.invalidateQueries({
      queryKey: queryKeys.global("config", "extras", "claude"),
    });
    void queryClient.invalidateQueries({
      queryKey: queryKeys.global("config", "backups", "cleanup"),
    });
    void queryClient.invalidateQueries({
      queryKey: queryKeys.global("config", "backups", "settings"),
    });
  }, [cleanupAction.phase, restoreCleanupAction.phase, restoreSettingsAction.phase, queryClient]);

  if (extrasQuery.isPending) return <EmptyState title="Loading cleanup candidates..." />;
  if (extrasQuery.isError) {
    return (
      <EmptyState title="Could not load cleanup candidates" body={extrasQuery.error.message} />
    );
  }

  return (
    <div className="us3-module">
      <header className="us3-module__header">
        <div>
          <h1>Cleanup & Restore</h1>
          <p>
            Remove deployed extras only after a cleanup backup is prepared, or restore prior
            backups.
          </p>
        </div>
        <div className="us3-toolbar">
          <button
            type="button"
            onClick={() => {
              setSelectionTouched(true);
              setSelectedPaths(new Set(staleExtras.map((extra) => extra.rel_path)));
            }}
          >
            Select stale
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectionTouched(true);
              setSelectedPaths(new Set(allExtras.map((extra) => extra.rel_path)));
            }}
          >
            Select all extras
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectionTouched(true);
              setSelectedPaths(new Set());
            }}
            disabled={selectedPaths.size === 0}
          >
            Clear
          </button>
          <button
            type="button"
            onClick={() => cleanupAction.prepare({ paths: Array.from(selectedPaths) })}
            disabled={selectedPaths.size === 0}
          >
            Remove {selectedPaths.size}
          </button>
        </div>
      </header>

      <section className="cleanup-command-strip">
        <div>
          <span className="us3-eyebrow">Removal review</span>
          <strong>{selectedPaths.size} queued for backup-first cleanup</strong>
          <p>
            {staleExtras.length} stale candidate(s), {unknownExtras} unknown extra(s). Unknown files
            stay unselected until you choose them.
          </p>
        </div>
        <ol className="deploy-command-strip__steps" aria-label="Cleanup workflow">
          <li className={selectedPaths.size > 0 ? "deploy-command-strip__step--done" : ""}>
            Select files
          </li>
          <li>Backup copy</li>
          <li>Remove originals</li>
          <li>Restore if needed</li>
        </ol>
      </section>

      <section className="cleanup-grid">
        <div className="cleanup-grid__main">
          {extrasQuery.data.groups.length === 0 ? (
            <EmptyState title="No deployed extras found" />
          ) : (
            extrasQuery.data.groups.map((group) => (
              <article key={group.component} className="cleanup-group">
                <h2>{group.label}</h2>
                <ul className="cleanup-list">
                  {group.extras.map((extra) => (
                    <li key={extra.rel_path} className="cleanup-list__item">
                      <label className="cleanup-list__select">
                        <input
                          type="checkbox"
                          checked={selectedPaths.has(extra.rel_path)}
                          onChange={(event) => {
                            setSelectionTouched(true);
                            setSelectedPaths((current) =>
                              updatePathSelection(
                                current,
                                extra.rel_path,
                                event.currentTarget.checked,
                              ),
                            );
                          }}
                        />
                        <span className="cleanup-list__path">{extra.rel_path}</span>
                      </label>
                      <span className="cleanup-list__classification">{extra.classification}</span>
                      <span className="cleanup-list__reason">{extra.reason}</span>
                    </li>
                  ))}
                </ul>
              </article>
            ))
          )}
        </div>

        <aside className="backup-panel">
          <RecoveryTimeline
            isLoading={cleanupBackups.isPending || settingsBackups.isPending}
            backups={backupTimeline}
            onRestore={(backup) =>
              backup.kind === "cleanup"
                ? restoreCleanupAction.prepare({ backup_id: backup.id })
                : restoreSettingsAction.prepare({ backup_id: backup.id })
            }
          />
        </aside>
      </section>

      <ConfirmDialog
        isOpen={cleanupAction.phase !== "idle" && cleanupAction.phase !== "succeeded"}
        actionTitle="Remove deployed extras"
        ticket={cleanupAction.ticket}
        phase={cleanupAction.phase}
        reviewNotice={cleanupAction.reviewNotice}
        error={cleanupAction.error}
        onConfirm={cleanupAction.confirm}
        onCancel={cleanupAction.reset}
      />
      <ConfirmDialog
        isOpen={restoreCleanupAction.phase !== "idle" && restoreCleanupAction.phase !== "succeeded"}
        actionTitle="Restore cleanup backup"
        ticket={restoreCleanupAction.ticket}
        phase={restoreCleanupAction.phase}
        reviewNotice={restoreCleanupAction.reviewNotice}
        error={restoreCleanupAction.error}
        onConfirm={restoreCleanupAction.confirm}
        onCancel={restoreCleanupAction.reset}
      />
      <ConfirmDialog
        isOpen={
          restoreSettingsAction.phase !== "idle" && restoreSettingsAction.phase !== "succeeded"
        }
        actionTitle="Restore settings backup"
        ticket={restoreSettingsAction.ticket}
        phase={restoreSettingsAction.phase}
        reviewNotice={restoreSettingsAction.reviewNotice}
        error={restoreSettingsAction.error}
        onConfirm={restoreSettingsAction.confirm}
        onCancel={restoreSettingsAction.reset}
      />
    </div>
  );
}

function RecoveryTimeline({
  isLoading,
  backups,
  onRestore,
}: {
  isLoading: boolean;
  backups: BackupSet[];
  onRestore: (backup: BackupSet) => void;
}) {
  return (
    <section className="recovery-timeline">
      <header className="recovery-timeline__header">
        <div>
          <span className="us3-eyebrow">Recovery history</span>
          <h2>Restore points</h2>
        </div>
        <span>{backups.length}</span>
      </header>
      {isLoading ? (
        <p className="backup-list__empty">Loading restore points...</p>
      ) : backups.length === 0 ? (
        <p className="backup-list__empty">No restore points available.</p>
      ) : (
        <ul>
          {backups.map((backup, index) => (
            <li key={`${backup.kind}-${backup.id}`} className="recovery-timeline__item">
              <span className="recovery-timeline__rail" aria-hidden="true">
                <span />
              </span>
              <div className="recovery-timeline__body">
                <div>
                  <StatePill
                    variant={backup.kind === "cleanup" ? "update" : "degraded"}
                    label={backup.kind}
                  />
                  {index === 0 ? <span className="recovery-timeline__latest">latest</span> : null}
                </div>
                <strong>
                  {backup.files_count} file{backup.files_count === 1 ? "" : "s"}
                </strong>
                <code>{backup.id}</code>
                <time dateTime={backup.created_at}>{formatBackupTime(backup.created_at)}</time>
              </div>
              <button type="button" onClick={() => onRestore(backup)} disabled={!backup.restorable}>
                Restore
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function formatBackupTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function updatePathSelection(current: Set<string>, path: string, checked: boolean): Set<string> {
  const next = new Set(current);
  if (checked) next.add(path);
  else next.delete(path);
  return next;
}
