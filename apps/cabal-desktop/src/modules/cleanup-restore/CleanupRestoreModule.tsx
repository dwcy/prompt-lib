// Cleanup & Restore console module: extras review + backup-first removal command strip, grouped
// extras table with stale-default indicators, and the recovery timeline restore panel — console
// token/card language matching PackageSecurityModule and ServicesModule.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { type BackupSet, useConfigBackups, useConfigExtras } from "@/api/config";
import { queryKeys } from "@/api/queryKeys";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import "./CleanupRestoreModule.css";

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
    <div className="clnr-console">
      <header className="clnr-header">
        <div className="clnr-header__intro">
          <h1>Cleanup & Restore</h1>
          <p>
            Remove deployed extras only after a cleanup backup is prepared, or restore prior
            backups.
          </p>
        </div>
        <div className="clnr-toolbar">
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
            className="clnr-toolbar__danger-btn"
            onClick={() => cleanupAction.prepare({ paths: Array.from(selectedPaths) })}
            disabled={selectedPaths.size === 0}
          >
            Remove {selectedPaths.size}
          </button>
        </div>
      </header>

      <section className="clnr-strip">
        <div className="clnr-strip__summary">
          <span className="clnr-eyebrow">Removal review</span>
          <strong>{selectedPaths.size} queued for backup-first cleanup</strong>
          <p>
            {staleExtras.length} stale candidate(s), {unknownExtras} unknown extra(s). Unknown files
            stay unselected until you choose them.
          </p>
        </div>
        <ol className="clnr-strip__steps" aria-label="Cleanup workflow">
          <li className={selectedPaths.size > 0 ? "clnr-strip__step--done" : ""}>Select files</li>
          <li>Backup copy</li>
          <li>Remove originals</li>
          <li>Restore if needed</li>
        </ol>
        <CardRefreshFooter>
          <RefreshButton
            label="cleanup candidates"
            onRefresh={() => void extrasQuery.refetch()}
            isFetching={extrasQuery.isFetching}
          />
        </CardRefreshFooter>
      </section>

      <section className="clnr-layout">
        <div className="clnr-layout__main">
          {extrasQuery.data.groups.length === 0 ? (
            <EmptyState title="No deployed extras found" />
          ) : (
            extrasQuery.data.groups.map((group) => (
              <article key={group.component} className="clnr-group">
                <h2>{group.label}</h2>
                <ul className="clnr-list">
                  {group.extras.map((extra) => (
                    <li key={extra.rel_path} className="clnr-list__item">
                      <label className="clnr-list__select">
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
                        <span className="clnr-list__path">{extra.rel_path}</span>
                      </label>
                      <span
                        className={
                          extra.classification === "stale"
                            ? "clnr-list__classification clnr-list__classification--stale"
                            : "clnr-list__classification"
                        }
                      >
                        {extra.classification}
                      </span>
                      <span className="clnr-list__reason">{extra.reason}</span>
                    </li>
                  ))}
                </ul>
              </article>
            ))
          )}
        </div>

        <aside className="clnr-layout__aside">
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

      <ConfirmDialog action={cleanupAction} actionTitle="Remove deployed extras" />
      <ConfirmDialog action={restoreCleanupAction} actionTitle="Restore cleanup backup" />
      <ConfirmDialog action={restoreSettingsAction} actionTitle="Restore settings backup" />
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
    <section className="clnr-recovery">
      <header className="clnr-recovery__header">
        <div className="clnr-recovery__header-intro">
          <span className="clnr-eyebrow">Recovery history</span>
          <h2>Restore points</h2>
        </div>
        <span className="clnr-recovery__count">{backups.length}</span>
      </header>
      {isLoading ? (
        <p className="clnr-recovery__empty">Loading restore points...</p>
      ) : backups.length === 0 ? (
        <p className="clnr-recovery__empty">No restore points available.</p>
      ) : (
        <ul className="clnr-recovery__list">
          {backups.map((backup, index) => (
            <li key={`${backup.kind}-${backup.id}`} className="clnr-recovery__item">
              <span className="clnr-recovery__rail" aria-hidden="true">
                <span />
              </span>
              <div className="clnr-recovery__body">
                <div className="clnr-recovery__body-head">
                  <StatePill
                    variant={backup.kind === "cleanup" ? "update" : "degraded"}
                    label={backup.kind}
                  />
                  {index === 0 ? <span className="clnr-recovery__latest">latest</span> : null}
                </div>
                <strong>
                  {backup.files_count} file{backup.files_count === 1 ? "" : "s"}
                </strong>
                <code>{backup.id}</code>
                <time dateTime={backup.created_at}>{formatBackupTime(backup.created_at)}</time>
              </div>
              <button
                type="button"
                className="clnr-recovery__restore"
                onClick={() => onRestore(backup)}
                disabled={!backup.restorable}
              >
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
