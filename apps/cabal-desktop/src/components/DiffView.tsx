// Renders unified diff text with add/del/hunk/meta line classes — no external diff dependency.
export interface DiffViewProps {
  diffText: string;
  emptyLabel?: string;
}

type DiffLineKind = "add" | "del" | "hunk" | "meta" | "context";

function classifyLine(line: string): DiffLineKind {
  if (line.startsWith("+++") || line.startsWith("---")) return "meta";
  if (line.startsWith("@@")) return "hunk";
  if (line.startsWith("+")) return "add";
  if (line.startsWith("-")) return "del";
  return "context";
}

export function DiffView({ diffText, emptyLabel = "No differences." }: DiffViewProps) {
  const lines = diffText.length > 0 ? diffText.split("\n") : [];

  if (lines.length === 0) {
    return <p className="diff-view__empty select-none">{emptyLabel}</p>;
  }

  return (
    <pre className="diff-view">
      {lines.map((line, index) => (
        <div
          // biome-ignore lint/suspicious/noArrayIndexKey: diff lines are a static, non-reorderable render of diffText
          key={index}
          className={`diff-view__line diff-view__line--${classifyLine(line)}`}
        >
          {line.length > 0 ? line : " "}
        </div>
      ))}
    </pre>
  );
}
