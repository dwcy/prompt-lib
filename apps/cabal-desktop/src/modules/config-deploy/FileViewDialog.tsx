// Reader for one deploy-tree file: its diff, the deployed copy, or this repo's source. Owns the
// queries and the view switches; the content itself is rendered by FileViewContent.
import { useState } from "react";
import {
  type ConfigFile,
  type ConfigTarget,
  useConfigDiff,
  useConfigFileContent,
} from "@/api/config";
import { RefreshButton } from "@/components/RefreshButton";
import { StatePill } from "@/components/StatePill";
import { useDialogFocusTrap } from "@/hooks/useDialogFocusTrap";
import { fileStateVariant } from "./deployPresentation";
import { FileViewContent } from "./FileViewContent";
import { availableTabs, FILE_VIEW_LABELS, type FileViewTab, initialTab } from "./fileViewTabs";

export interface FileViewDialogProps {
  target: ConfigTarget;
  file: ConfigFile;
  initialView?: FileViewTab;
  onClose: () => void;
}

export function FileViewDialog({ target, file, initialView, onClose }: FileViewDialogProps) {
  const [tab, setTab] = useState<FileViewTab>(initialView ?? initialTab(file));
  const [raw, setRaw] = useState(false);
  const { dialogRef, closeButtonRef } = useDialogFocusTrap(onClose);

  const diffQuery = useConfigDiff(target, tab === "diff" ? file.rel_path : null);
  const contentQuery = useConfigFileContent(
    target,
    tab === "diff" ? null : file.rel_path,
    tab === "diff" ? "deployed" : tab,
  );
  const active = tab === "diff" ? diffQuery : contentQuery;
  const content = tab === "diff" ? null : (contentQuery.data ?? null);
  const isMarkdown = content?.markdown != null;

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
            {content !== null ? (
              <code className="cfg-file-view__abs">{content.abs_path}</code>
            ) : null}
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
          <div className="segmented-control" role="tablist" aria-label="File view">
            {availableTabs(file).map((option) => (
              <button
                key={option}
                type="button"
                role="tab"
                aria-selected={tab === option}
                className={`select-none${tab === option ? " is-active" : ""}`}
                onClick={() => setTab(option)}
              >
                {FILE_VIEW_LABELS[option]}
              </button>
            ))}
          </div>
          {isMarkdown ? (
            <button
              type="button"
              className={`cfg-file-view__raw-toggle select-none${raw ? " is-active" : ""}`}
              aria-pressed={raw}
              onClick={() => setRaw(!raw)}
            >
              {raw ? "Rendered" : "Raw markdown"}
            </button>
          ) : null}
          {content?.truncated === true ? (
            <span className="cfg-file-view__meta">Truncated at the preview limit</span>
          ) : null}
          <RefreshButton
            label="this file"
            onRefresh={() => void active.refetch()}
            isFetching={active.isFetching}
          />
        </div>

        <div className="cfg-file-view__body">
          <FileViewContent
            tab={tab}
            raw={raw}
            isPending={active.isPending}
            error={active.error}
            diff={diffQuery.data ?? null}
            file={content}
          />
        </div>
      </div>
    </div>
  );
}
