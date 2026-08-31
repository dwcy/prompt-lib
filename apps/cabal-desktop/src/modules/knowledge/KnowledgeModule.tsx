// Knowledge module: console graph layout — toolbar-filtered graph + evidence drawer, plus the
// search / context-pack / reports workbenches, restyled to the Cabal Console design language.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  type KnowledgeEdge,
  type KnowledgeGraphFilters,
  type KnowledgeNode,
  useKnowledgeGraph,
  useKnowledgeSummary,
} from "@/api/knowledge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { useAction } from "@/hooks/useAction";
import { ContextPackPanel } from "@/modules/knowledge/components/ContextPackPanel";
import { GraphWorkbench } from "@/modules/knowledge/components/GraphWorkbench";
import { KnowledgeHeader } from "@/modules/knowledge/components/KnowledgeHeader";
import {
  type KnowledgeTab,
  KnowledgeTabsBar,
} from "@/modules/knowledge/components/KnowledgeTabsBar";
import { ReportsPanel } from "@/modules/knowledge/components/ReportsPanel";
import { SearchPanel } from "@/modules/knowledge/components/SearchPanel";
import "./KnowledgeModule.css";

export function KnowledgeModule() {
  const queryClient = useQueryClient();
  const summaryQuery = useKnowledgeSummary();
  const [tab, setTab] = useState<KnowledgeTab>("graph");
  const [retrievalBrief, setRetrievalBrief] = useState("");
  const [graphFilters, setGraphFilters] = useState<KnowledgeGraphFilters>({
    query: "",
    type: "",
    relation: "",
  });
  const graphQuery = useKnowledgeGraph(graphFilters);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<KnowledgeEdge | null>(null);
  const [lastJobId, setLastJobId] = useState<string | null>(null);
  const exportAction = useAction("knowledge.export");
  const doctorAction = useAction("knowledge.doctor");
  const indexAction = useAction("knowledge.index");

  useEffect(() => {
    const jobId = exportAction.jobId ?? doctorAction.jobId ?? indexAction.jobId;
    if (
      exportAction.phase !== "succeeded" &&
      doctorAction.phase !== "succeeded" &&
      indexAction.phase !== "succeeded"
    ) {
      return;
    }
    if (jobId === null) return;
    setLastJobId(jobId);
    queryClient.invalidateQueries({ queryKey: ["cabal", "global", "knowledge"] });
  }, [
    doctorAction.jobId,
    doctorAction.phase,
    exportAction.phase,
    exportAction.jobId,
    indexAction.phase,
    indexAction.jobId,
    queryClient,
  ]);

  useEffect(() => {
    if (selectedId !== null && graphQuery.data?.nodes.some((node) => node.id === selectedId)) {
      return;
    }
    const first = graphQuery.data?.nodes[0] ?? null;
    setSelectedId(first?.id ?? null);
    setSelectedEdge(first === null ? null : firstConnectedEdge(first, graphQuery.data?.edges));
  }, [graphQuery.data, selectedId]);

  if (summaryQuery.isPending) {
    return <EmptyState title="Loading knowledge catalog..." />;
  }

  if (summaryQuery.isError) {
    return (
      <EmptyState title="Could not load knowledge catalog" body={summaryQuery.error.message} />
    );
  }

  const summary = summaryQuery.data;
  const graph = graphQuery.data;
  const typeOptions = Object.keys(summary.counts.by_type).sort();
  const relationOptions = Object.keys(summary.counts.by_relation).sort();

  function handleSelectNode(node: KnowledgeNode) {
    setSelectedId(node.id);
    setSelectedEdge(firstConnectedEdge(node, graph?.edges));
  }

  return (
    <div className="km-module">
      <KnowledgeHeader
        summary={summary}
        onExport={() => exportAction.prepare({})}
        onDoctor={() => doctorAction.prepare({})}
        onIndex={() => indexAction.prepare({ force: false })}
        onRefresh={() => void summaryQuery.refetch()}
        isFetching={summaryQuery.isFetching}
      />

      {lastJobId !== null ? <JobPane jobId={lastJobId} /> : null}

      <KnowledgeTabsBar tab={tab} onTabChange={setTab} />

      {tab === "graph" ? (
        <GraphWorkbench
          graph={graph}
          isPending={graphQuery.isPending}
          error={graphQuery.error}
          filters={graphFilters}
          setFilters={setGraphFilters}
          typeOptions={typeOptions}
          relationOptions={relationOptions}
          selectedId={selectedId}
          selectedEdge={selectedEdge}
          onSelect={handleSelectNode}
          onSelectEdge={setSelectedEdge}
          onRefresh={() => void graphQuery.refetch()}
          isFetching={graphQuery.isFetching}
        />
      ) : null}
      {tab === "search" ? (
        <SearchPanel
          semanticAvailable={summary.semantic_available}
          query={retrievalBrief}
          onQueryChange={setRetrievalBrief}
          onTrace={(result) => {
            setRetrievalBrief(result.title);
            setGraphFilters({ query: result.title, type: result.type, relation: "" });
            setTab("graph");
          }}
          onBuildPack={(result) => {
            setRetrievalBrief(result.title);
            setTab("packs");
          }}
        />
      ) : null}
      {tab === "packs" ? (
        <ContextPackPanel query={retrievalBrief} onQueryChange={setRetrievalBrief} />
      ) : null}
      {tab === "reports" ? (
        <ReportsPanel task={retrievalBrief} onTaskChange={setRetrievalBrief} />
      ) : null}

      <ConfirmDialog action={exportAction} actionTitle="Export OKF Bundle" />
      <ConfirmDialog action={doctorAction} actionTitle="Validate OKF Bundle" />
      <ConfirmDialog action={indexAction} actionTitle="Rebuild OKF Index" />
    </div>
  );
}

function firstConnectedEdge(
  node: KnowledgeNode,
  edges: KnowledgeEdge[] | undefined,
): KnowledgeEdge | null {
  if (edges === undefined) return null;
  return edges.find((edge) => edge.from === node.id || edge.to === node.id) ?? null;
}
