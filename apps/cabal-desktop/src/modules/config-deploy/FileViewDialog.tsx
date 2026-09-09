// Full-file viewer for the deploy tree: reads one file end to end, either the copy deployed to
// the target or this repo's source for it. Unchanged files have no diff to show, so this is the
// only way to actually read them.
import { useState } from "react";
import {
  type ConfigFile,
  type ConfigFileSide,
  type ConfigTarget,
  useConfigFileContent,
} from "@/api/config";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { useDialogFocusTrap } from "@/hooks/useDialogFocusTrap";
import { fileStateVariant } from "./deployPresentation";

export interface FileViewDialogProps {
  target: ConfigTarget;
  file: ConfigFile;
  onClose: () => void;
}

const SIDE_LABELS: Record<ConfigFileSide, string> = {
  deployed: "Deployed",
  source: "Repo source",
};

export function FileViewDialog({ target, file, onClose }: FileViewDialogProps) {
  // A new file exists only in the repo — opening on the deployed side would show "not there yet".
  const [side, setSide] = useState<ConfigFileSide>(file.state === "new" ? "source" : "deployed");
  const { dialogRef, closeButtonRef } = useDialogFocusTrap(onClose);
  const fileQuery = useConfigFileContent(target, file.rel_path, side);

  const data = fileQuery.data ?? null;
  const lineCount = data?.content?.split("\n").length ?? 0;

  return (
    <div
      className="confirm-dialog-overlay"
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="confirm-dialog cfg-file-view"
        role="dialog"
        aria-modal="true"
        aria-label={`${file.rel_path} contents`}
        tabIndex={-1}
      >
        <header className="confirm-dialog__header">
          <div>
            <span className="confirm-dialog__eyebrow">{target} config file</span>
            <h2 className="confirm-dialog__title cfg-file-view__path">{file.rel_path}</h2>
            {data !== null ? <code className="cfg-file-view__abs">{data.abs_path}</code> : null}
          </div>
          <div className="cfg-file-view__header-side">
            <StatePill variant={fileStateVariant(file.state)} label={file.state} />
            <button
              ref={closeButtonRef}
              type="button"
              className="job-tray__close"
              onClick={onClose}
              aria-label="Close file"
              title="Close file"
            >
              <span aria-hidden="true">×</span>
            </button>
          </div>
        </header>

        <div className="cfg-file-view__toolbar">
          <div className="segmented-control" role="tablist" aria-label="File side">
            {(["deployed", "source"] as ConfigFileSide[]).map((option) => (
              <button
                key={option}
                type="button"
                role="tab"
                aria-selected={side === option}
                className={`select-none${side === option ? " is-active" : ""}`}
                onClick={() => setSide(option)}
              >
                {SIDE_LABELS[option]}
              </button>
            ))}
          </div>
          {data?.content != null ? (
            <span className="cfg-file-view__meta">
              {lineCount} lines
              {data.truncated ? " · truncated at the preview limit" : ""}
            </span>
          ) : null}
        </div>

        <div className="cfg-file-view__body">
          {fileQuery.isPending ? (
            <EmptyState title="Reading the file" animated />
          ) : fileQuery.isError ? (
            <EmptyState title="Could not read that file" body={fileQuery.error.message} />
          ) : !fileQuery.data.exists ? (
            <EmptyState
              title={
                side === "deployed"
                  ? "Not deployed to the target yet"
                  : "No source for this file in the repo"
              }
              body={fileQuery.data.abs_path}
            />
          ) : fileQuery.data.binary ? (
            <EmptyState title="Binary file" body="There is nothing to show as text." />
          ) : (
            <pre className="cfg-file-view__content">
              <code>{fileQuery.data.content}</code>
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
