// Configuration surfaces card: Global/Local tab switcher over real config-file presence facts
// reported by /api/claude-info.
import { useState } from "react";
import type { ClaudeInfoPayload } from "@/api/observability";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { RefreshButton } from "@/components/RefreshButton";
import { type ConfigScope, groupDocumentsByScope } from "../configSurfaces";

export interface ConfigSurfacesCardProps {
  documents: ClaudeInfoPayload["documents"];
  onRefresh: () => void;
  isFetching: boolean;
}

export function ConfigSurfacesCard({ documents, onRefresh, isFetching }: ConfigSurfacesCardProps) {
  const [scope, setScope] = useState<ConfigScope>("global");
  const grouped = groupDocumentsByScope(documents);
  const rows = grouped[scope];

  return (
    <section className="ccfg-surfaces-card">
      <header className="ccfg-surfaces-card__header">
        <b>Configuration surfaces</b>
        <div className="segmented-control" role="tablist" aria-label="Configuration scope">
          <button
            type="button"
            role="tab"
            aria-selected={scope === "global"}
            className={`select-none${scope === "global" ? " is-active" : ""}`}
            onClick={() => setScope("global")}
          >
            Global · ~/.claude
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={scope === "local"}
            className={`select-none${scope === "local" ? " is-active" : ""}`}
            onClick={() => setScope("local")}
          >
            Local · ./.claude
          </button>
        </div>
      </header>
      {rows.length === 0 ? (
        <p className="ccfg-surfaces-card__empty">No {scope} config surfaces reported.</p>
      ) : (
        <div className="ccfg-surfaces-rows">
          {rows.map((doc) => (
            <div key={doc.path} className="ccfg-surfaces-row">
              <span className={`ccfg-dot ${doc.present ? "ccfg-dot--ok" : "ccfg-dot--missing"}`} />
              <span className="ccfg-surfaces-row__name">{doc.label}</span>
              <span className="ccfg-surfaces-row__desc">{doc.path}</span>
              <span
                className={`ccfg-surfaces-row__state ccfg-mono ${doc.present ? "ccfg-tone-ok" : "ccfg-tone-warning"}`}
              >
                {doc.present ? `${doc.line_count} lines` : "missing"}
              </span>
            </div>
          ))}
        </div>
      )}
      <CardRefreshFooter>
        <RefreshButton label="config surfaces" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </section>
  );
}
