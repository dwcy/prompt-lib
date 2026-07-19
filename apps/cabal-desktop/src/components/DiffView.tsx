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

  const kinds = lines.map(classifyLine);
  const additions = kinds.filter((kind) => kind === "add").length;
  const deletions = kinds.filter((kind) => kind === "del").length;

  return (
    <div className="diff-view-frame">
      <fieldset className="diff-view__stats select-none">
        <legend className="visually-hidden">Change summary</legend>
        <span className="diff-view__stat diff-view__stat--add">+{additions}</span>
        <span className="diff-view__stat diff-view__stat--del">-{deletions}</span>
      </fieldset>
      <section aria-label="Unified diff">
        <pre className="diff-view">
          <code>
            {lines.map((line, index) => (
              <span
                // biome-ignore lint/suspicious/noArrayIndexKey: diff lines are a static, non-reorderable render of diffText
                key={index}
                className={`diff-view__line diff-view__line--${kinds[index]}`}
              >
                {line.length > 0 ? line : " "}
              </span>
            ))}
          </code>
        </pre>
      </section>
    </div>
  );
}
