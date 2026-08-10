// Graph tab: toolbar (search/type/relation/counts) above a graph-panel + evidence-drawer grid.
import { useMemo } from "react";
import type {
  KnowledgeEdge,
  KnowledgeGraph,
  KnowledgeGraphFilters,
  KnowledgeNode,
} from "@/api/knowledge";
import { EmptyState } from "@/components/EmptyState";
import { EvidenceDrawer } from "@/modules/knowledge/components/EvidenceDrawer";
import { GraphPanel } from "@/modules/knowledge/components/GraphPanel";
import { KnowledgeToolbar } from "@/modules/knowledge/components/KnowledgeToolbar";

export interface GraphWorkbenchProps {
  graph: KnowledgeGraph | undefined;
  isPending: boolean;
  error: Error | null;
  filters: KnowledgeGraphFilters;
  setFilters: (filters: KnowledgeGraphFilters) => void;
  typeOptions: string[];
  relationOptions: string[];
  selectedId: string | null;
  selectedEdge: KnowledgeEdge | null;
  onSelect: (node: KnowledgeNode) => void;
  onSelectEdge: (edge: KnowledgeEdge) => void;
}

export function GraphWorkbench({
  graph,
  isPending,
  error,
  filters,
  setFilters,
  typeOptions,
  relationOptions,
  selectedId,
  selectedEdge,
  onSelect,
  onSelectEdge,
}: GraphWorkbenchProps) {
  const nodesById = useMemo(
    () => new Map((graph?.nodes ?? []).map((node) => [node.id, node])),
    [graph],
  );

  if (isPending) return <EmptyState title="Loading graph..." />;
  if (error !== null) return <EmptyState title="Could not load graph" body={error.message} />;
  if (graph === undefined) return null;

  return (
    <section className="km-graph-tab">
      <KnowledgeToolbar
        filters={filters}
        onFiltersChange={setFilters}
        typeOptions={typeOptions}
        relationOptions={relationOptions}
        nodeCount={graph.nodes.length}
        edgeCount={graph.edges.length}
      />
      <div className="km-graph-grid">
        <GraphPanel
          graph={graph}
          selectedId={selectedId}
          selectedEdgeId={selectedEdge?.id ?? null}
          highlight={filters.query}
          onSelect={onSelect}
          onSelectEdge={onSelectEdge}
        />
        <EvidenceDrawer edge={selectedEdge} nodesById={nodesById} />
      </div>
    </section>
  );
}
