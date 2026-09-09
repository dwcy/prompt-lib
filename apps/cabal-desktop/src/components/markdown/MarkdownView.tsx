// A whole parsed markdown document: the text before the first heading, then every section with
// its heading at the level the file gave it.
import type { MarkdownDocument } from "@/api/markdown";
import { MarkdownBlock } from "./MarkdownBlock";

export interface MarkdownViewProps {
  document: MarkdownDocument;
}

const HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"] as const;

export function MarkdownView({ document }: MarkdownViewProps) {
  return (
    <article className="md-view">
      {document.preamble.map((block, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: a parsed document is a static, non-reorderable render of one file
        <MarkdownBlock key={`pre-${block.type}-${index}`} block={block} />
      ))}
      {document.sections.map((section) => {
        const Heading = HEADING_TAGS[Math.min(section.level, HEADING_TAGS.length) - 1];
        return (
          <section key={section.anchor} className="md-view__section">
            <Heading className={`md-view__heading md-view__heading--h${section.level}`}>
              {section.title}
            </Heading>
            {section.blocks.map((block, index) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: a parsed document is a static, non-reorderable render of one file
              <MarkdownBlock key={`${section.anchor}-${block.type}-${index}`} block={block} />
            ))}
          </section>
        );
      })}
    </article>
  );
}
