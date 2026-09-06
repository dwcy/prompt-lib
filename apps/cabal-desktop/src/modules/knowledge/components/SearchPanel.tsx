// Search tab: query panel (mode toggle + starter prompts) and a result-card stack with
// trace-in-graph / build-context-pack handoffs.
import { useState } from "react";
import { type KnowledgeSearchResult, useKnowledgeSearch } from "@/api/knowledge";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";

type SearchMode = "fulltext" | "semantic";

const RETRIEVAL_STARTERS = [
  "How is configuration deployed?",
  "Which agents and skills own this area?",
  "What safety checks apply before a write?",
];

export interface SearchPanelProps {
  semanticAvailable: boolean;
  query: string;
  onQueryChange: (query: string) => void;
  onTrace: (result: KnowledgeSearchResult) => void;
  onBuildPack: (result: KnowledgeSearchResult) => void;
}

export function SearchPanel({
  semanticAvailable,
  query,
  onQueryChange,
  onTrace,
  onBuildPack,
}: SearchPanelProps) {
  const [mode, setMode] = useState<SearchMode>("fulltext");
  const searchQuery = useKnowledgeSearch(query, mode);
  return (
    <section className="km-two-column">
      <div className="km-card km-query-panel">
        <span className="km-eyebrow">Retrieval</span>
        <h2>Search the indexed catalog</h2>
        <textarea
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          rows={5}
          placeholder="Describe a concept, feature, or relationship"
        />
        <div className="km-starters">
          {RETRIEVAL_STARTERS.map((starter) => (
            <button key={starter} type="button" onClick={() => onQueryChange(starter)}>
              {starter}
            </button>
          ))}
        </div>
        <fieldset className="km-segmented">
          <legend className="km-vh">Search mode</legend>
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
      <div className="km-result-stack">
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
        <CardRefreshFooter>
          <RefreshButton
            label="search results"
            onRefresh={() => void searchQuery.refetch()}
            isFetching={searchQuery.isFetching}
          />
        </CardRefreshFooter>
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
    <article className="km-card km-result-card">
      <header>
        <span className="km-result-card__kind">
          {result.type}
          {result.rank !== undefined ? ` · #${result.rank}` : ""}
        </span>
        <strong>{result.title}</strong>
        {result.score !== undefined ? <small>{result.score.toFixed(3)}</small> : null}
      </header>
      <p>{result.resource}</p>
      {result.snippet ? <small>{result.snippet}</small> : null}
      <footer className="km-result-card__handoff">
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
