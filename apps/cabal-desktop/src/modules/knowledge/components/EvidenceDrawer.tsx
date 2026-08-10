// Sticky evidence drawer: shows the selected edge's routing evidence, or the click-to-inspect
// hint when nothing is selected yet.
import type { KnowledgeEdge, KnowledgeNode } from "@/api/knowledge";

export interface EvidenceDrawerProps {
  edge: KnowledgeEdge | null;
  nodesById: Map<string, KnowledgeNode>;
}

const HINT_TEXT = "Click any edge in the map to inspect its routing evidence.";

export function EvidenceDrawer({ edge, nodesById }: EvidenceDrawerProps) {
  if (edge === null) {
    return (
      <aside className="km-evidence" aria-label="Routing evidence">
        <p className="km-evidence__hint">{HINT_TEXT}</p>
      </aside>
    );
  }

  const sourceLabel = nodesById.get(edge.from)?.label ?? edge.from;
  const targetLabel = nodesById.get(edge.to)?.label ?? edge.to;

  return (
    <aside className="km-evidence" aria-label="Routing evidence">
      <div className="km-evidence__head">
        <span className="km-evidence__kind">{edge.relation}</span>
        <span className="km-evidence__confidence">{edge.confidence}</span>
      </div>
      <div className="km-evidence__route">
        {sourceLabel} <span className="km-evidence__arrow">{"→"}</span> {targetLabel}
      </div>
      <p className="km-evidence__reason">{edge.reason}</p>
      <div className="km-evidence__section-title">EVIDENCE</div>
      <div className="km-evidence__cards">
        {edge.evidence.length === 0 ? (
          <p className="km-evidence__empty">No evidence recorded for this relation.</p>
        ) : (
          edge.evidence.map((item, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: evidence entries carry no stable id
            <EvidenceCard key={index} evidence={item} />
          ))
        )}
      </div>
      <div className="km-evidence__footer">{HINT_TEXT}</div>
    </aside>
  );
}

function EvidenceCard({ evidence }: { evidence: Record<string, unknown> }) {
  const ref = readString(evidence, ["resource", "ref", "source"]);
  const text = readString(evidence, ["text", "snippet", "body"]);
  return (
    <div className="km-evidence__card">
      {ref !== null ? <div className="km-evidence__card-ref">{ref}</div> : null}
      <div className="km-evidence__card-text">{text ?? "No excerpt available."}</div>
    </div>
  );
}

function readString(source: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = source[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return null;
}
