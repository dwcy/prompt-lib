// Renders the typed blocks the backend parsed out of a skill body: paragraphs, code fences,
// lists, tables, quotes and rules. One switch, no markdown engine.
import type { SkillBlock } from "@/api/agentSkills";
import { renderInline } from "./skillInline";

export interface SkillBlocksProps {
  blocks: SkillBlock[];
}

function Block({ block }: { block: SkillBlock }) {
  switch (block.type) {
    case "paragraph":
      return <p className="skill-block__text">{renderInline(block.text)}</p>;
    case "code":
      return (
        <div className="skill-block__code">
          {block.language !== null ? (
            <span className="skill-block__code-lang select-none">{block.language}</span>
          ) : null}
          <pre>{block.text}</pre>
        </div>
      );
    case "list":
      return block.ordered ? (
        <ol className="skill-block__list">
          {block.items.map((item, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: parsed markdown blocks are a static, non-reorderable render of one skill file
            <li key={`${index}-${item.text}`} data-depth={item.depth}>
              {renderInline(item.text)}
            </li>
          ))}
        </ol>
      ) : (
        <ul className="skill-block__list">
          {block.items.map((item, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: parsed markdown blocks are a static, non-reorderable render of one skill file
            <li key={`${index}-${item.text}`} data-depth={item.depth}>
              {renderInline(item.text)}
            </li>
          ))}
        </ul>
      );
    case "table":
      return (
        <div className="skill-block__table-scroll">
          <table className="skill-block__table">
            <thead>
              <tr>
                {block.header.map((cell, index) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: parsed markdown blocks are a static, non-reorderable render of one skill file
                  <th key={`${index}-${cell}`}>{renderInline(cell)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, rowIndex) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: parsed markdown blocks are a static, non-reorderable render of one skill file
                <tr key={`row-${rowIndex}-${row[0] ?? ""}`}>
                  {row.map((cell, cellIndex) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: parsed markdown blocks are a static, non-reorderable render of one skill file
                    <td key={`cell-${cellIndex}-${cell}`}>{renderInline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "quote":
      return <blockquote className="skill-block__quote">{renderInline(block.text)}</blockquote>;
    default:
      return <hr className="skill-block__divider" />;
  }
}

export function SkillBlocks({ blocks }: SkillBlocksProps) {
  return (
    <div className="skill-blocks">
      {blocks.map((block, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: parsed markdown blocks are a static, non-reorderable render of one skill file
        <Block key={`${block.type}-${index}`} block={block} />
      ))}
    </div>
  );
}
