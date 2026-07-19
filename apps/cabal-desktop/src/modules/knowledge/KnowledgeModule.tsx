import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  type ContextPack,
  type KnowledgeEdge,
  type KnowledgeGraphFilters,
  type KnowledgeNode,
  type KnowledgeSearchResult,
  useKnowledgeContextPack,
  useKnowledgeGraph,
  useKnowledgePreflight,
  useKnowledgeSearch,
  useKnowledgeSummary,
  useKnowledgeUsage,
} from "@/api/knowledge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import { GraphCanvas } from "@/modules/knowledge/GraphCanvas";

type KnowledgeTab = "graph" | "search" | "packs" | "reports";
type SearchMode = "fulltext" | "semantic";
type Budget = "tiny" | "focused" | "full";

const DEFAULT_QUERY = "";
const RETRIEVAL_STARTERS = [
  "How is configuration deployed?",
  "Which agents and skills own this area?",
  "What safety checks apply before a write?",
];
const KNOWLEDGE_STAGES: Array<{
  key: KnowledgeTab;
  label: string;
  purpose: string;
}> = [
  { key: "graph", label: "Graph", purpose: "Explore" },
  { key: "search", label: "Search", purpose: "Retrieve" },
  { key: "packs", label: "Context pack", purpose: "Assemble" },
  { key: "reports", label: "Reports", purpose: "Verify" },
];

export function KnowledgeModule() {
  const queryClient = useQueryClient();
  const summaryQuery = useKnowledgeSummary();
  const [tab, setTab] = useState<KnowledgeTab>("graph");
  const [retrievalBrief, setRetrievalBrief] = useState(DEFAULT_QUERY);
  const [graphFilters, setGraphFilters] = useState<KnowledgeGraphFilters>({
    query: "",
    type: "",
    relation: "",
  });
  const graphQuery = useKnowledgeGraph(graphFilters);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
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
    setSelectedNode(first);
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

  return (
    <div className="knowledge-workspace">
      <section className="knowledge-command-center">
        <div>
          <span className="us3-eyebrow">OKF knowledge fabric</span>
          <h1>Knowledge & retrieval</h1>
          <p>
            The graph, index, context packs, preflight reports, and usage ledger are all tied to the
            shared OKF service layer.
          </p>
        </div>
        <div className="knowledge-command-center__metrics">
          <Metric label="concepts" value={String(summary.counts.nodes)} />
          <Metric label="relations" value={String(summary.counts.edges)} />
          <Metric label="usage" value={String(summary.usage_count)} />
          <StatePill variant={summary.index_available ? "ok" : "degraded"} label="index" />
          <StatePill variant={summary.semantic_available ? "ok" : "degraded"} label="semantic" />
        </div>
        <div className="knowledge-command-center__actions">
          <button type="button" onClick={() => exportAction.prepare({})}>
            Export bundle
          </button>
          <button type="button" onClick={() => doctorAction.prepare({})}>
            Validate bundle
          </button>
          <button type="button" onClick={() => indexAction.prepare({ force: false })}>
            Rebuild index
          </button>
        </div>
      </section>

      {!summary.available ? (
        <section className="knowledge-empty-runway">
          <div>
            <span className="us3-eyebrow">Bundle missing</span>
            <strong>Build the project knowledge fabric</strong>
            <p>Export generates the graph and documents required by retrieval and indexing.</p>
          </div>
          <button type="button" onClick={() => exportAction.prepare({})}>
            Export first bundle
          </button>
        </section>
      ) : null}

      {lastJobId !== null ? <JobPane jobId={lastJobId} /> : null}

      <fieldset className="knowledge-tabs">
        <legend className="visually-hidden">Knowledge view</legend>
        {KNOWLEDGE_STAGES.map((stage, index) => (
          <button
            key={stage.key}
            type="button"
            className={tab === stage.key ? "is-active" : undefined}
            aria-pressed={tab === stage.key}
            onClick={() => setTab(stage.key)}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{stage.label}</strong>
            <small>{stage.purpose}</small>
          </button>
        ))}
      </fieldset>

      {tab === "graph" ? (
        <GraphWorkbench
          graph={graph}
          isPending={graphQuery.isPending}
          error={graphQuery.error}
          filters={graphFilters}
          setFilters={setGraphFilters}
          typeOptions={typeOptions}
          relationOptions={relationOptions}
          selectedNode={selectedNode}
          selectedEdges={graph?.edges ?? []}
          onSelect={(node) => {
            setSelectedId(node.id);
            setSelectedNode(node);
          }}
        />
      ) : null}
      {tab === "search" ? (
        <SearchWorkbench
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
        <ContextWorkbench query={retrievalBrief} onQueryChange={setRetrievalBrief} />
      ) : null}
      {tab === "reports" ? (
        <ReportsWorkbench task={retrievalBrief} onTaskChange={setRetrievalBrief} />
      ) : null}

      <ConfirmDialog
        isOpen={exportAction.phase !== "idle" && exportAction.phase !== "succeeded"}
        actionTitle="Export OKF Bundle"
        ticket={exportAction.ticket}
        phase={exportAction.phase}
        reviewNotice={exportAction.reviewNotice}
        error={exportAction.error}
        onConfirm={exportAction.confirm}
        onCancel={exportAction.reset}
      />
      <ConfirmDialog
        isOpen={doctorAction.phase !== "idle" && doctorAction.phase !== "succeeded"}
        actionTitle="Validate OKF Bundle"
        ticket={doctorAction.ticket}
        phase={doctorAction.phase}
        reviewNotice={doctorAction.reviewNotice}
        error={doctorAction.error}
        onConfirm={doctorAction.confirm}
        onCancel={doctorAction.reset}
      />
      <ConfirmDialog
        isOpen={indexAction.phase !== "idle" && indexAction.phase !== "succeeded"}
        actionTitle="Rebuild OKF Index"
        ticket={indexAction.ticket}
        phase={indexAction.phase}
        reviewNotice={indexAction.reviewNotice}
        error={indexAction.error}
        onConfirm={indexAction.confirm}
        onCancel={indexAction.reset}
      />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <span>
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

interface GraphWorkbenchProps {
  graph: ReturnType<typeof useKnowledgeGraph>["data"];
  isPending: boolean;
  error: Error | null;
  filters: KnowledgeGraphFilters;
  setFilters: (filters: KnowledgeGraphFilters) => void;
  typeOptions: string[];
  relationOptions: string[];
  selectedNode: KnowledgeNode | null;
  selectedEdges: KnowledgeEdge[];
  onSelect: (node: KnowledgeNode) => void;
}

function GraphWorkbench({
  graph,
  isPending,
  error,
  filters,
  setFilters,
  typeOptions,
  relationOptions,
  selectedNode,
  selectedEdges,
  onSelect,
}: GraphWorkbenchProps) {
  const connectedEdges = useMemo(
    () =>
      selectedNode === null
        ? []
        : selectedEdges.filter(
            (edge) => edge.from === selectedNode.id || edge.to === selectedNode.id,
          ),
    [selectedEdges, selectedNode],
  );

  if (isPending) return <EmptyState title="Loading graph..." />;
  if (error !== null) return <EmptyState title="Could not load graph" body={error.message} />;
  if (graph === undefined) return null;

  return (
    <section className="knowledge-graph-workbench">
      <div className="knowledge-filter-rail">
        <label>
          Search
          <input
            value={filters.query}
            onChange={(event) => setFilters({ ...filters, query: event.target.value })}
            placeholder="agent, skill, spec..."
          />
        </label>
        <label>
          Type
          <select
            value={filters.type}
            onChange={(event) => setFilters({ ...filters, type: event.target.value })}
          >
            <option value="">All types</option>
            {typeOptions.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label>
          Relation
          <select
            value={filters.relation}
            onChange={(event) => setFilters({ ...filters, relation: event.target.value })}
          >
            <option value="">All relations</option>
            {relationOptions.map((relation) => (
              <option key={relation} value={relation}>
                {relation}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => setFilters({ query: "", type: "", relation: "" })}>
          Reset
        </button>
      </div>

      <GraphCanvas
        graph={graph}
        selectedId={selectedNode?.id ?? null}
        highlight={filters.query}
        onSelect={onSelect}
      />

      <KnowledgeInspector node={selectedNode} edges={connectedEdges} />
    </section>
  );
}

function KnowledgeInspector({
  node,
  edges,
}: {
  node: KnowledgeNode | null;
  edges: KnowledgeEdge[];
}) {
  if (node === null) {
    return (
      <aside className="knowledge-inspector">
        <EmptyState title="Select a concept" />
      </aside>
    );
  }
  return (
    <aside className="knowledge-inspector">
      <span className="us3-eyebrow">{node.type}</span>
      <h2>{node.label}</h2>
      <p>{node.resource}</p>
      <div className="knowledge-tag-row">
        {node.tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <dl className="knowledge-metrics">
        <div>
          <dt>incoming</dt>
          <dd>{String(node.metrics.incoming ?? 0)}</dd>
        </div>
        <div>
          <dt>outgoing</dt>
          <dd>{String(node.metrics.outgoing ?? 0)}</dd>
        </div>
      </dl>
      <div className="knowledge-edge-stack">
        {edges.length === 0 ? (
          <EmptyState title="No visible relations" />
        ) : (
          edges.slice(0, 12).map((edge) => (
            <article key={edge.id} className="knowledge-edge-card">
              <strong>{edge.relation}</strong>
              <span>
                {edge.from}
                {" -> "}
                {edge.to}
              </span>
              <p>{edge.reason}</p>
              {edge.evidence[0] !== undefined ? (
                <small>{String(edge.evidence[0].text ?? edge.evidence[0].resource ?? "")}</small>
              ) : null}
            </article>
          ))
        )}
      </div>
    </aside>
  );
}

function SearchWorkbench({
  semanticAvailable,
  query,
  onQueryChange,
  onTrace,
  onBuildPack,
}: {
  semanticAvailable: boolean;
  query: string;
  onQueryChange: (query: string) => void;
  onTrace: (result: KnowledgeSearchResult) => void;
  onBuildPack: (result: KnowledgeSearchResult) => void;
}) {
  const [mode, setMode] = useState<SearchMode>("fulltext");
  const searchQuery = useKnowledgeSearch(query, mode);
  return (
    <section className="knowledge-two-column">
      <div className="knowledge-query-panel">
        <span className="us3-eyebrow">Retrieval</span>
        <h2>Search the indexed catalog</h2>
        <textarea
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          rows={5}
          placeholder="Describe a concept, feature, or relationship"
        />
        <div className="knowledge-query-starters">
          {RETRIEVAL_STARTERS.map((starter) => (
            <button key={starter} type="button" onClick={() => onQueryChange(starter)}>
              {starter}
            </button>
          ))}
        </div>
        <fieldset className="segmented-control">
          <legend className="visually-hidden">Search mode</legend>
          <button
            type="button"
            className={mode === "fulltext" ? "is-active" : undefined}
            aria-pressed={mode === "fulltext"}
            onClick={() => setMode("fulltext")}
          >
            Full text
          </button>
          <button
            type="button"
            className={mode === "semantic" ? "is-active" : undefined}
            aria-pressed={mode === "semantic"}
            onClick={() => setMode("semantic")}
            disabled={!semanticAvailable}
          >
            Semantic
          </button>
        </fieldset>
      </div>
      <div className="knowledge-result-stack">
        {searchQuery.isPending ? (
          <EmptyState title="Enter a query to search" />
        ) : searchQuery.isError ? (
          <EmptyState title="Search failed" body={searchQuery.error.message} />
        ) : searchQuery.data.available ? (
          searchQuery.data.results.map((result) => (
            <SearchResultCard
              key={result.id}
              result={result}
              onTrace={() => onTrace(result)}
              onBuildPack={() => onBuildPack(result)}
            />
          ))
        ) : (
          <EmptyState title={searchQuery.data.status} body={searchQuery.data.message} />
        )}
      </div>
    </section>
  );
}

function SearchResultCard({
  result,
  onTrace,
  onBuildPack,
}: {
  result: KnowledgeSearchResult;
  onTrace: () => void;
  onBuildPack: () => void;
}) {
  return (
    <article className="knowledge-result-card">
      <header>
        <span>
          {result.type}
          {result.rank !== undefined ? ` · #${result.rank}` : ""}
        </span>
        <strong>{result.title}</strong>
        {result.score !== undefined ? <small>{result.score.toFixed(3)}</small> : null}
      </header>
      <p>{result.resource}</p>
      {result.snippet ? <small>{result.snippet}</small> : null}
      <footer className="knowledge-result-card__handoff">
        <button type="button" onClick={onTrace}>
          Trace in graph
        </button>
        <button type="button" onClick={onBuildPack}>
          Build context pack
        </button>
      </footer>
    </article>
  );
}

function ContextWorkbench({
  query,
  onQueryChange,
}: {
  query: string;
  onQueryChange: (query: string) => void;
}) {
  const [budget, setBudget] = useState<Budget>("focused");
  const contextQuery = useKnowledgeContextPack(query, budget);
  return (
    <section className="knowledge-two-column">
      <div className="knowledge-query-panel">
        <span className="us3-eyebrow">Context compiler</span>
        <h2>Build a budgeted pack</h2>
        <textarea
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          rows={6}
          placeholder="Describe the task that needs grounded project context"
        />
        <fieldset className="segmented-control">
          <legend className="visually-hidden">Budget</legend>
          {(["tiny", "focused", "full"] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={budget === item ? "is-active" : undefined}
              aria-pressed={budget === item}
              onClick={() => setBudget(item)}
            >
              {item}
            </button>
          ))}
        </fieldset>
      </div>
      <div className="knowledge-pack-view">
        {contextQuery.isPending ? (
          <EmptyState title="Waiting for a query" />
        ) : contextQuery.isError ? (
          <EmptyState title="Context pack failed" body={contextQuery.error.message} />
        ) : contextQuery.data.pack === null ? (
          <EmptyState title={contextQuery.data.status} body={contextQuery.data.message} />
        ) : (
          <ContextPackView pack={contextQuery.data.pack} />
        )}
      </div>
    </section>
  );
}

function ContextPackView({ pack }: { pack: ContextPack }) {
  const [copied, setCopied] = useState(false);
  const serialized = JSON.stringify(pack, null, 2);
  return (
    <>
      <div className="knowledge-pack-summary">
        <div>
          <strong>{pack.estimated_tokens} estimated tokens</strong>
          <span>{pack.matches.length} matches</span>
          <span>{pack.expanded_concepts.length} expansions</span>
        </div>
        <div className="knowledge-pack-summary__actions">
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard.writeText(serialized).then(() => setCopied(true));
            }}
          >
            {copied ? "Copied" : "Copy JSON"}
          </button>
          <button type="button" onClick={() => downloadContextPack(serialized)}>
            Export JSON
          </button>
        </div>
      </div>
      <div className="knowledge-pack-columns">
        <PackColumn title="Matches" items={pack.matches} />
        <PackColumn title="Expanded" items={pack.expanded_concepts} />
      </div>
      <div className="knowledge-why">
        {pack.why.map((reason) => (
          <p key={reason}>{reason}</p>
        ))}
      </div>
    </>
  );
}

function downloadContextPack(serialized: string) {
  const url = URL.createObjectURL(new Blob([serialized], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "cabal-context-pack.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function PackColumn({ title, items }: { title: string; items: ContextPack["matches"] }) {
  return (
    <section>
      <h3>{title}</h3>
      {items.length === 0 ? (
        <EmptyState title="None" />
      ) : (
        items.map((item) => (
          <article key={item.id} className="knowledge-result-card">
            <strong>{item.title ?? item.id}</strong>
            <p>{item.resource ?? ""}</p>
            <small>{item.snippet ?? item.body_preview ?? item.description ?? ""}</small>
          </article>
        ))
      )}
    </section>
  );
}

function ReportsWorkbench({
  task,
  onTaskChange,
}: {
  task: string;
  onTaskChange: (task: string) => void;
}) {
  const preflightQuery = useKnowledgePreflight(task);
  const usageQuery = useKnowledgeUsage(20);
  return (
    <section className="knowledge-two-column">
      <div className="knowledge-query-panel">
        <span className="us3-eyebrow">Preflight</span>
        <h2>Scope and context risk</h2>
        <textarea
          value={task}
          onChange={(event) => onTaskChange(event.target.value)}
          rows={5}
          placeholder="Describe the implementation task to scope"
        />
        {preflightQuery.data !== undefined ? (
          <div className="knowledge-preflight-card">
            <header>
              <strong>Scope {preflightQuery.data.report.scope}</strong>
              <StatePill
                variant={preflightQuery.data.report.risk_flags.length > 0 ? "degraded" : "ok"}
                label={`${preflightQuery.data.report.recommended_budget} context`}
              />
            </header>
            <span>Index: {preflightQuery.data.report.index_state}</span>
            <div className="knowledge-preflight-card__signals">
              {preflightQuery.data.report.risk_flags.map((flag) => (
                <span key={flag} className="is-risk">
                  {flag}
                </span>
              ))}
              {preflightQuery.data.report.likely_areas.map((area) => (
                <span key={area}>{area}</span>
              ))}
            </div>
            {preflightQuery.data.report.why.map((reason) => (
              <p key={reason}>{reason}</p>
            ))}
          </div>
        ) : null}
      </div>
      <div className="knowledge-usage-ledger">
        <header>
          <span className="us3-eyebrow">Usage ledger</span>
          <strong>{usageQuery.data?.total_entries ?? 0} recorded retrieval calls</strong>
        </header>
        {usageQuery.isError ? (
          <EmptyState title="Could not load usage" body={usageQuery.error.message} />
        ) : (usageQuery.data?.entries.length ?? 0) === 0 ? (
          <EmptyState title="No usage entries" body="The OKF ledger is empty for this project." />
        ) : (
          usageQuery.data?.entries.map((entry) => (
            <article key={`${entry.timestamp}-${entry.action}-${entry.query_preview}`}>
              <header>
                <strong>{entry.action}</strong>
                <StatePill
                  variant={entry.cache_state.toLowerCase().includes("hit") ? "ok" : "unavailable"}
                  label={entry.cache_state}
                />
              </header>
              <span>
                {entry.entrypoint} / {entry.budget} / {entry.estimated_tokens} tokens /{" "}
                {entry.duration_ms} ms
              </span>
              <p>{entry.query_preview}</p>
              <time dateTime={entry.timestamp}>{formatKnowledgeTime(entry.timestamp)}</time>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function formatKnowledgeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
