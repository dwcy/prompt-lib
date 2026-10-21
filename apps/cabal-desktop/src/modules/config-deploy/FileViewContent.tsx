// The three readings of one deploy-tree file — its diff, the deployed copy, this repo's source —
// rendered from query state the dialog owns. Markdown arrives parsed, so a .md file reads as a
// document unless `raw` asks for the source text. Presentation only: no fetching here.
import type { ConfigDiff, ConfigFileContent } from "@/api/config";
import { DiffView } from "@/components/DiffView";
import { EmptyState } from "@/components/EmptyState";
import { MarkdownView } from "@/components/markdown/MarkdownView";
import type { FileViewTab } from "./fileViewTabs";

export interface FileViewContentProps {
  tab: FileViewTab;
  raw: boolean;
  isPending: boolean;
  error: Error | null;
  diff: ConfigDiff | null;
  file: ConfigFileContent | null;
}

function MissingSide({ side, absPath }: { side: ConfigFileContent["side"]; absPath: string }) {
  const title =
    side === "deployed" ? "Not deployed to the target yet" : "No source for this file in the repo";
  return <EmptyState title={title} body={absPath} />;
}

export function FileViewContent({ tab, raw, isPending, error, diff, file }: FileViewContentProps) {
  if (isPending) return <EmptyState title="Reading the file" animated />;
  if (error !== null) return <EmptyState title="Could not read that file" body={error.message} />;

  if (tab === "diff") {
    if (diff === null) return <EmptyState title="No diff for this file" />;
    return (
      <div className="cfg-file-view__diff">
        <DiffView diffText={diff.diff_text} emptyLabel="No differences." />
      </div>
    );
  }

  if (file === null) return <EmptyState title="No content to show" />;
  if (!file.exists) return <MissingSide side={file.side} absPath={file.abs_path} />;
  if (file.binary) {
    return <EmptyState title="Binary file" body="There is nothing to show as text." />;
  }
  if (file.markdown !== null && !raw) {
    return (
      <div className="cfg-file-view__document">
        <MarkdownView document={file.markdown} />
      </div>
    );
  }
  return (
    <pre className="cfg-file-view__content">
      <code>{file.content}</code>
    </pre>
  );
}
