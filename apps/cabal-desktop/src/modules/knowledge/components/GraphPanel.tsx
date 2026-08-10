// Graph card: surface-deep canvas frame hosting GraphCanvas plus the top-left type legend overlay.
import type { KnowledgeEdge, KnowledgeGraph, KnowledgeNode } from "@/api/knowledge";
import { GraphLegend } from "@/modules/knowledge/components/GraphLegend";
import { GraphCanvas } from "@/modules/knowledge/GraphCanvas";

export interface GraphPanelProps {
  graph: KnowledgeGraph;
  selectedId: string | null;
  selectedEdgeId: string | null;
  highlight: string;
  onSelect: (node: KnowledgeNode) => void;
  onSelectEdge: (edge: KnowledgeEdge) => void;
}

export function GraphPanel({
  graph,
  selectedId,
  selectedEdgeId,
  highlight,
  onSelect,
  onSelectEdge,
}: GraphPanelProps) {
  const types = [...new Set(graph.nodes.map((node) => node.type))];

  return (
    <div className="km-graph">
      <GraphLegend types={types} />
      <GraphCanvas
        graph={graph}
        selectedId={selectedId}
        selectedEdgeId={selectedEdgeId}
        highlight={highlight}
        onSelect={onSelect}
        onSelectEdge={onSelectEdge}
      />
    </div>
  );
}
