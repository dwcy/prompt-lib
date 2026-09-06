// Renders the full EffectPreview for a prepared action ticket; destructive styling when removals
// are non-empty; surfaces the 409 state_changed "re-review" flow per the action-safety contract.
import { type ReactNode, useEffect, useId, useRef } from "react";
import type { UseActionResult } from "@/hooks/useAction";

export interface ConfirmDialogProps {
  /** The action being confirmed; the dialog reads its ticket, phase, and callbacks. */
  action: UseActionResult;
  actionTitle: string;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function ConfirmDialog({ action, actionTitle }: ConfirmDialogProps) {
  const { ticket, phase, reviewNotice, error } = action;
  const onConfirm = action.confirm;
  const onCancel = action.reset;
  // An action is being confirmed from the moment it leaves idle until it succeeds.
  const isVisible = phase !== "idle" && phase !== "succeeded";
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const onCancelRef = useRef(onCancel);
  const isBusyRef = useRef(false);
  const titleId = useId();

  onCancelRef.current = onCancel;

  const preview = ticket?.effect_preview ?? null;
  const isDestructive = (preview?.removals.length ?? 0) > 0;
  const isBusy = phase === "preparing" || phase === "executing";
  isBusyRef.current = isBusy;

  useEffect(() => {
    if (!isVisible) return;

    previouslyFocused.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (cancelButtonRef.current?.disabled) {
      dialogRef.current?.focus();
    } else {
      cancelButtonRef.current?.focus();
    }

    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape" && !isBusyRef.current) {
        event.preventDefault();
        onCancelRef.current();
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
  }, [isVisible]);

  const confirmLabel =
    phase === "preparing"
      ? "Preparing preview…"
      : phase === "executing"
        ? `${actionTitle}…`
        : actionTitle;

  if (!isVisible) return null;

  return (
    <div className="confirm-dialog-overlay" role="presentation">
      <div
        ref={dialogRef}
        className={`confirm-dialog${isDestructive ? " confirm-dialog--destructive" : ""}`}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="confirm-dialog__header">
          <div>
            <span className="confirm-dialog__eyebrow select-none">Prepared action</span>
            <h2 id={titleId} className="confirm-dialog__title select-none">
              {actionTitle}
            </h2>
          </div>
          <span
            className={
              isDestructive
                ? "confirm-dialog__risk confirm-dialog__risk--destructive"
                : "confirm-dialog__risk"
            }
          >
            {isDestructive ? "destructive" : "review required"}
          </span>
        </header>

        {reviewNotice ? (
          <p className="confirm-dialog__review-notice" role="alert">
            State changed since this preview was prepared. Review the updated effect before
            confirming.
          </p>
        ) : null}

        {error !== null ? (
          <p className="confirm-dialog__error" role="alert">
            {error.message}
          </p>
        ) : null}

        {preview === null ? (
          <p className="confirm-dialog__loading select-none">Preparing preview…</p>
        ) : (
          <div className="confirm-dialog__preview">
            <p className="confirm-dialog__summary">{preview.summary}</p>

            <dl className="confirm-dialog__metrics">
              <div>
                <dt>Commands</dt>
                <dd>{preview.commands.length}</dd>
              </div>
              <div>
                <dt>Files</dt>
                <dd>{preview.files_changed.length}</dd>
              </div>
              <div>
                <dt>Scopes</dt>
                <dd>{preview.scopes.length}</dd>
              </div>
              <div data-risk={preview.removals.length > 0 ? "destructive" : "none"}>
                <dt>Removals</dt>
                <dd>{preview.removals.length}</dd>
              </div>
            </dl>

            <ol className="confirm-dialog__runway" aria-label="Action execution sequence">
              <li className="is-complete">
                <span>01</span>
                <strong>Effect prepared</strong>
                <small>{reviewNotice ? "preview refreshed" : "snapshot locked"}</small>
              </li>
              <li className={phase === "executing" ? "is-complete" : "is-current"}>
                <span>02</span>
                <strong>Recheck state</strong>
                <small>digest must still match</small>
              </li>
              <li className={phase === "executing" ? "is-current" : undefined}>
                <span>03</span>
                <strong>Execute + audit</strong>
                <small>single-use ticket</small>
              </li>
            </ol>

            <div className="confirm-dialog__detail-grid">
              {preview.commands.length > 0 ? (
                <PreviewSection title={`Commands (${preview.commands.length})`}>
                  <ul className="confirm-dialog__list">
                    {preview.commands.map((command) => (
                      <li key={command}>
                        <code>{command}</code>
                      </li>
                    ))}
                  </ul>
                </PreviewSection>
              ) : null}

              {preview.files_changed.length > 0 ? (
                <PreviewSection title={`Files changed (${preview.files_changed.length})`}>
                  <ul className="confirm-dialog__list">
                    {preview.files_changed.map((file) => (
                      <li key={file}>
                        <code>{file}</code>
                      </li>
                    ))}
                  </ul>
                </PreviewSection>
              ) : null}

              <PreviewSection title="Scopes">
                <p>{preview.scopes.length > 0 ? preview.scopes.join(", ") : "None"}</p>
              </PreviewSection>

              <PreviewSection title="Backup">
                <p>
                  {preview.backup === null || preview.backup === undefined ? (
                    "None"
                  ) : (
                    <code>{preview.backup}</code>
                  )}
                </p>
              </PreviewSection>

              {preview.removals.length > 0 ? (
                <PreviewSection title={`Removals (${preview.removals.length})`}>
                  <ul className="confirm-dialog__list confirm-dialog__list--destructive">
                    {preview.removals.map((removal) => (
                      <li key={removal}>
                        <code>{removal}</code>
                      </li>
                    ))}
                  </ul>
                </PreviewSection>
              ) : null}
            </div>
          </div>
        )}

        <div className="confirm-dialog__actions select-none">
          <button ref={cancelButtonRef} type="button" onClick={onCancel} disabled={isBusy}>
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isBusy || preview === null}
            className={isDestructive ? "confirm-dialog__confirm--destructive" : undefined}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

interface PreviewSectionProps {
  title: string;
  children: ReactNode;
}

function PreviewSection({ title, children }: PreviewSectionProps) {
  return (
    <section className="confirm-dialog__section">
      <h3 className="confirm-dialog__section-title select-none">{title}</h3>
      {children}
    </section>
  );
}
