// Inline markdown -> React nodes: `code`, **bold**, *italic*, and [text](url). Deliberately
// small — these four cover the config documents we render, and no markdown engine is pulled in.
import type { ReactNode } from "react";

const INLINE_PATTERN = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\[[^\]\n]+\]\([^)\s]+\))|(\*[^*\n]+\*)/g;
const LINK_PARTS = /^\[([^\]]+)\]\(([^)\s]+)\)$/;

function token(text: string, key: number): ReactNode {
  if (text.startsWith("`")) {
    return (
      <code key={key} className="md-inline__code">
        {text.slice(1, -1)}
      </code>
    );
  }
  if (text.startsWith("**")) {
    return <strong key={key}>{text.slice(2, -2)}</strong>;
  }
  const link = LINK_PARTS.exec(text);
  if (link !== null) {
    // A desktop webview must not navigate away from the app, so the target lives in the tooltip.
    return (
      <span key={key} className="md-inline__link" title={link[2]}>
        {link[1]}
      </span>
    );
  }
  return <em key={key}>{text.slice(1, -1)}</em>;
}

/** Render one line/paragraph of markdown as inline React nodes. */
export function renderMarkdownInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let key = 0;
  for (const match of text.matchAll(INLINE_PATTERN)) {
    const start = match.index ?? 0;
    if (start > cursor) {
      nodes.push(text.slice(cursor, start));
    }
    nodes.push(token(match[0], key));
    key += 1;
    cursor = start + match[0].length;
  }
  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }
  return nodes;
}
