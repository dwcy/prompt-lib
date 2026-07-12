// Renders the full EffectPreview for a prepared action ticket; destructive styling when removals
// are non-empty; surfaces the 409 state_changed "re-review" flow per the action-safety contract.
import type { ReactNode } from "react";
import type { ApiError } from "@/api/errors";
import type { ConfirmationTicket } from "@/api/schemas";
import type { ActionPhase } from "@/hooks/useAction";

export interface ConfirmDialogProps {
  isOpen: boolean;
  actionTitle: string;
  ticket: ConfirmationTicket | null;
  phase: ActionPhase;
  reviewNotice: boolean;
  error: ApiError | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  isOpen,
  actionTitle,
  ticket,
  phase,
  reviewNotice,
  error,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!isOpen) return null;

  const preview = ticket?.effect_preview ?? null;
  const isDestructive = (preview?.removals.length ?? 0) > 0;
  const isBusy = phase === "preparing" || phase === "executing";

  return (
    <div className="confirm-dialog-overlay" role="presentation">
      <div
        className={`confirm-dialog${isDestructive ? " confirm-dialog--destructive" : ""}`}
        role="alertdialog"
        aria-modal="true"
        aria-label={actionTitle}
      >
        <h2 className="confirm-dialog__title select-none">{actionTitle}</h2>

        {reviewNotice ? (
          <p className="confirm-dialog__review-notice" role="alert">
            State changed since this preview was prepared — re-review before confirming.
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

            {preview.commands.length > 0 ? (
              <PreviewSection title="Commands">
                <ul className="confirm-dialog__list">
                  {preview.commands.map((command) => (
                    <li key={command}>{command}</li>
                  ))}
                </ul>
              </PreviewSection>
            ) : null}

            {preview.files_changed.length > 0 ? (
              <PreviewSection title="Files changed">
                <ul className="confirm-dialog__list">
                  {preview.files_changed.map((file) => (
                    <li key={file}>{file}</li>
                  ))}
                </ul>
              </PreviewSection>
            ) : null}

            <PreviewSection title="Scopes">
              <p>{preview.scopes.length > 0 ? preview.scopes.join(", ") : "None"}</p>
            </PreviewSection>

            <PreviewSection title="Backup">
              <p>{preview.backup ?? "None"}</p>
            </PreviewSection>

            {preview.removals.length > 0 ? (
              <PreviewSection title="Removals">
                <ul className="confirm-dialog__list confirm-dialog__list--destructive">
                  {preview.removals.map((removal) => (
                    <li key={removal}>{removal}</li>
                  ))}
                </ul>
              </PreviewSection>
            ) : null}
          </div>
        )}

        <div className="confirm-dialog__actions select-none">
          <button type="button" onClick={onCancel} disabled={isBusy}>
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isBusy || preview === null}
            className={isDestructive ? "confirm-dialog__confirm--destructive" : undefined}
          >
            {phase === "executing" ? "Executing…" : "Confirm"}
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
