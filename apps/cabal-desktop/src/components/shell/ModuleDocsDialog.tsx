// "Read more about this screen" dialog behind the header docs icon: the module's one-line
// operation summary, then the release-note entries that document it (what it is for, how to
// use it, what to watch out for).
import { useEffect, useId, useRef } from "react";
import { moduleDocEntries } from "@/components/shell/moduleDocs";
import { MODULE_OPERATION_SUMMARIES, type ModuleKey, requireModule } from "@/modules/registry";

export interface ModuleDocsDialogProps {
  moduleKey: ModuleKey;
  onClose: () => void;
}

const FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function ModuleDocsDialog({ moduleKey, onClose }: ModuleDocsDialogProps) {
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

  const module = requireModule(moduleKey);
  const entries = moduleDocEntries(moduleKey);

  return (
    <div className="module-docs-overlay">
      <button
        type="button"
        className="module-docs-overlay__backdrop"
        aria-label="Close"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="module-docs"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="module-docs__header">
          <div>
            <span className="module-docs__eyebrow select-none">About this screen</span>
            <h2 id={titleId} className="module-docs__title select-none">
              {module.title}
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="module-docs__close"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </header>

        <p className="module-docs__summary">{MODULE_OPERATION_SUMMARIES[moduleKey]}</p>

        <div className="module-docs__body">
          {entries.length === 0 ? (
            <p className="module-docs__empty">
              No walkthrough is written for this screen yet. Reference → Release news lists every
              screen that has one.
            </p>
          ) : (
            entries.map((entry) => (
              <article key={entry.title} className="module-docs__entry">
                <h3>{entry.title}</h3>
                <p>{entry.purpose}</p>
                {entry.steps.length > 0 ? (
                  <ol className="module-docs__steps">
                    {entry.steps.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                ) : null}
                {entry.note !== undefined ? (
                  <p className="module-docs__note">{entry.note}</p>
                ) : null}
              </article>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
