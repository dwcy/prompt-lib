// Command header card: title/description, node/edge/usage metrics + index/semantic state pills,
// bundle actions, and the "bundle missing" runway banner shown when no OKF export exists yet.
import type { KnowledgeSummary } from "@/api/knowledge";
import { StatePill } from "@/components/StatePill";

export interface KnowledgeHeaderProps {
  summary: KnowledgeSummary;
  onExport: () => void;
  onDoctor: () => void;
  onIndex: () => void;
}

export function KnowledgeHeader({ summary, onExport, onDoctor, onIndex }: KnowledgeHeaderProps) {
  return (
    <>
      <section className="km-header">
        <div className="km-header__intro">
          <span className="km-eyebrow">OKF knowledge fabric</span>
          <h1>Knowledge & retrieval</h1>
          <p>
            The graph, index, context packs, preflight reports, and usage ledger are all tied to the
            shared OKF service layer.
          </p>
        </div>
        <div className="km-header__metrics">
          <Metric label="concepts" value={summary.counts.nodes} />
          <Metric label="relations" value={summary.counts.edges} />
          <Metric label="usage" value={summary.usage_count} />
          <StatePill variant={summary.index_available ? "ok" : "degraded"} label="index" />
          <StatePill variant={summary.semantic_available ? "ok" : "degraded"} label="semantic" />
        </div>
        <div className="km-header__actions">
          <button type="button" onClick={onExport}>
            Export bundle
          </button>
          <button type="button" onClick={onDoctor}>
            Validate bundle
          </button>
          <button type="button" onClick={onIndex}>
            Rebuild index
          </button>
        </div>
      </section>

      {!summary.available ? (
        <section className="km-empty-runway">
          <div>
            <span className="km-eyebrow">Bundle missing</span>
            <strong>Build the project knowledge fabric</strong>
            <p>Export generates the graph and documents required by retrieval and indexing.</p>
          </div>
          <button type="button" onClick={onExport}>
            Export first bundle
          </button>
        </section>
      ) : null}
    </>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <span className="km-header__metric">
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}
