// Modal listing every backend module reported by GET /api/health, opened from the header health
// strip; modules needing attention sort to the top so the reason for "backend degraded" is first.
import { useEffect, useId, useRef } from "react";
import type { ModuleHealth } from "@/api/schemas";
import { StatePill } from "@/components/StatePill";
import { findModule } from "@/modules/registry";

export interface HealthModulesDialogProps {
  modules: ModuleHealth[];
  onClose: () => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

const ATTENTION_STATES: ReadonlySet<ModuleHealth["state"]> = new Set([
  "degraded",
  "failed",
  "unavailable",
]);

function needsAttention(module: ModuleHealth): boolean {
  return ATTENTION_STATES.has(module.state);
}

function moduleLabel(module: ModuleHealth): string {
  return findModule(module.module)?.title ?? module.module;
}

function formatLastSuccess(lastSuccessAt: string | null): string {
  if (lastSuccessAt === null) return "never succeeded";
  const parsed = new Date(lastSuccessAt);
  if (Number.isNaN(parsed.getTime())) return "last OK unknown";
  return `last OK ${parsed.toTimeString().slice(0, 8)}`;
}

export function HealthModulesDialog({ modules, onClose }: HealthModulesDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const titleId = useId();

  onCloseRef.current = onClose;

  useEffect(() => {
    previouslyFocused.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || dialogRef.current === null) return;

      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusable.length === 0) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused.current?.focus();
    };
  }, []);

  const attention = modules.filter(needsAttention);
  const healthy = modules.filter((module) => !needsAttention(module));
  const ordered = [...attention, ...healthy];
  const summary =
    attention.length === 0
      ? `All ${modules.length} modules reporting OK.`
      : `${attention.length} of ${modules.length} modules need attention.`;

  return (
    <div
      className="confirm-dialog-overlay"
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="confirm-dialog health-modules"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="confirm-dialog__header">
          <div>
            <span className="job-tray__eyebrow">Backend health</span>
            <h2 id={titleId}>Modules</h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="job-tray__close"
            onClick={onClose}
            aria-label="Close modules"
            title="Close modules"
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        <p className="health-modules__summary">{summary}</p>

        <ul className="health-modules__list">
          {ordered.map((module) => (
            <li key={module.module} className="health-modules__row">
              <div className="health-modules__identity">
                <b>{moduleLabel(module)}</b>
                <small className="health-modules__meta">{module.module}</small>
              </div>
              <div className="health-modules__status">
                <StatePill variant={module.state} />
                <small className="health-modules__meta">
                  {module.detail || formatLastSuccess(module.last_success_at)}
                </small>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
