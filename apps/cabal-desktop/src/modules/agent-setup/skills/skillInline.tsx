// Inline markdown -> React nodes for skill bodies: `code`, **bold**, *italic*, and [text](url).
// Deliberately tiny: skill instructions lean on these four and nothing else, and rendering them
// as real spans is what turns a wall of markdown into something readable.
import type { ReactNode } from "react";

const INLINE_PATTERN = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\[[^\]\n]+\]\([^)\s]+\))|(\*[^*\n]+\*)/g;
const LINK_PARTS = /^\[([^\]]+)\]\(([^)\s]+)\)$/;

function token(text: string, key: number): ReactNode {
  if (text.startsWith("`")) {
    return (
      <code key={key} className="skill-inline__code">
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
      <span key={key} className="skill-inline__link" title={link[2]}>
        {link[1]}
      </span>
    );
  }
  return <em key={key}>{text.slice(1, -1)}</em>;
}

/** Render one line/paragraph of markdown as inline React nodes. */
export function renderInline(text: string): ReactNode[] {
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
