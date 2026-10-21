// One parsed markdown block as markup: paragraph, code fence, list, table, quote or rule.
// One switch, no markdown engine — the parsing already happened on the backend.
import type { MarkdownBlock as Block } from "@/api/markdown";
import { renderMarkdownInline } from "./markdownInline";

export interface MarkdownBlockProps {
  block: Block;
}

function ListBlock({ block }: { block: Extract<Block, { type: "list" }> }) {
  const items = block.items.map((item, index) => (
    // biome-ignore lint/suspicious/noArrayIndexKey: a parsed document is a static, non-reorderable render of one file
    <li key={`${index}-${item.text}`} data-depth={item.depth}>
      {renderMarkdownInline(item.text)}
    </li>
  ));
  return block.ordered ? (
    <ol className="md-block__list">{items}</ol>
  ) : (
    <ul className="md-block__list">{items}</ul>
  );
}

function TableBlock({ block }: { block: Extract<Block, { type: "table" }> }) {
  return (
    <div className="md-block__table-scroll">
      <table className="md-block__table">
        <thead>
          <tr>
            {block.header.map((cell, index) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: a parsed document is a static, non-reorderable render of one file
              <th key={`${index}-${cell}`}>{renderMarkdownInline(cell)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, rowIndex) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: a parsed document is a static, non-reorderable render of one file
            <tr key={`row-${rowIndex}-${row[0] ?? ""}`}>
              {row.map((cell, cellIndex) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: a parsed document is a static, non-reorderable render of one file
                <td key={`cell-${cellIndex}-${cell}`}>{renderMarkdownInline(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MarkdownBlock({ block }: MarkdownBlockProps) {
  switch (block.type) {
    case "paragraph":
      return <p className="md-block__text">{renderMarkdownInline(block.text)}</p>;
    case "code":
      return (
        <div className="md-block__code">
          {block.language !== null ? (
            <span className="md-block__code-lang select-none">{block.language}</span>
          ) : null}
          <pre>{block.text}</pre>
        </div>
      );
    case "list":
      return <ListBlock block={block} />;
    case "table":
      return <TableBlock block={block} />;
    case "quote":
      return (
        <blockquote className="md-block__quote">{renderMarkdownInline(block.text)}</blockquote>
      );
    default:
      return <hr className="md-block__divider" />;
  }
}
