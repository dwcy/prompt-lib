// Context pack tab: budget picker + query panel, and the compiled pack (matches/expanded/why)
// with copy-to-clipboard and JSON export.
import { useState } from "react";
import { type ContextPack, useKnowledgeContextPack } from "@/api/knowledge";
import { EmptyState } from "@/components/EmptyState";

type Budget = "tiny" | "focused" | "full";
const BUDGETS: Budget[] = ["tiny", "focused", "full"];

export interface ContextPackPanelProps {
  query: string;
  onQueryChange: (query: string) => void;
}

export function ContextPackPanel({ query, onQueryChange }: ContextPackPanelProps) {
  const [budget, setBudget] = useState<Budget>("focused");
  const contextQuery = useKnowledgeContextPack(query, budget);
  return (
    <section className="km-two-column">
      <div className="km-card km-query-panel">
        <span className="km-eyebrow">Context compiler</span>
        <h2>Build a budgeted pack</h2>
        <textarea
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          rows={6}
          placeholder="Describe the task that needs grounded project context"
        />
        <fieldset className="km-segmented">
          <legend className="km-vh">Budget</legend>
          {BUDGETS.map((item) => (
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
      <div className="km-pack-view">
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
    <div className="km-card km-pack-card">
      <div className="km-pack-summary">
        <div>
          <strong>{pack.estimated_tokens} estimated tokens</strong>
          <span>{pack.matches.length} matches</span>
          <span>{pack.expanded_concepts.length} expansions</span>
        </div>
        <div className="km-pack-summary__actions">
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
      <div className="km-pack-columns">
        <PackColumn title="Matches" items={pack.matches} />
        <PackColumn title="Expanded" items={pack.expanded_concepts} />
      </div>
      <div className="km-pack-why">
        {pack.why.map((reason) => (
          <p key={reason}>{reason}</p>
        ))}
      </div>
    </div>
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
    <section className="km-pack-column">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <EmptyState title="None" />
      ) : (
        items.map((item) => (
          <article key={item.id} className="km-result-card">
            <strong>{item.title ?? item.id}</strong>
            <p>{item.resource ?? ""}</p>
            <small>{item.snippet ?? item.body_preview ?? item.description ?? ""}</small>
          </article>
        ))
      )}
    </section>
  );
}
