import { useEffect, useRef, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { useJobTrayStore } from "@/stores/jobTray";

export function JobTray() {
  const [isOpen, setIsOpen] = useState(false);
  const trayRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const jobIds = useJobTrayStore((state) => state.jobIds);
  const removeJob = useJobTrayStore((state) => state.removeJob);

  useEffect(() => {
    if (!isOpen) return;

    function closeAndRestoreFocus(): void {
      setIsOpen(false);
      triggerRef.current?.focus();
    }

    function onKeyDown(event: KeyboardEvent): void {
      if (event.key !== "Escape") return;
      event.preventDefault();
      closeAndRestoreFocus();
    }

    function onPointerDown(event: PointerEvent): void {
      if (!(event.target instanceof Node) || trayRef.current?.contains(event.target)) return;
      closeAndRestoreFocus();
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [isOpen]);

  return (
    <div ref={trayRef} className="job-tray">
      <button
        ref={triggerRef}
        type="button"
        className="job-tray__trigger"
        aria-expanded={isOpen}
        aria-controls="global-job-tray"
        onClick={() => setIsOpen((current) => !current)}
      >
        Activity
        {jobIds.length > 0 ? <span className="job-tray__count">{jobIds.length}</span> : null}
      </button>

      {isOpen ? (
        <aside id="global-job-tray" className="job-tray__panel" aria-label="Activity tray">
          <header className="job-tray__header">
            <div>
              <span className="job-tray__eyebrow">Background work</span>
              <h2>Activity</h2>
            </div>
            <div className="job-tray__header-actions">
              <button
                type="button"
                className="job-tray__close"
                onClick={() => {
                  setIsOpen(false);
                  triggerRef.current?.focus();
                }}
                aria-label="Close activity"
                title="Close activity"
              >
                <span aria-hidden="true">×</span>
              </button>
            </div>
          </header>

          <div className="job-tray__body">
            {jobIds.length === 0 ? (
              <EmptyState
                title="No background activity"
                body="Running and completed jobs appear here."
              />
            ) : (
              jobIds.map((jobId) => (
                <JobPane key={jobId} jobId={jobId} onDismiss={() => removeJob(jobId)} />
              ))
            )}
          </div>
        </aside>
      ) : null}
    </div>
  );
}
