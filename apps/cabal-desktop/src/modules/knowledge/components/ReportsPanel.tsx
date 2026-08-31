// Reports tab: preflight scope/risk card driven by a task description, plus the usage ledger
// of recorded retrieval calls.
import { useKnowledgePreflight, useKnowledgeUsage } from "@/api/knowledge";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { StatePill } from "@/components/StatePill";

export interface ReportsPanelProps {
  task: string;
  onTaskChange: (task: string) => void;
}

export function ReportsPanel({ task, onTaskChange }: ReportsPanelProps) {
  const preflightQuery = useKnowledgePreflight(task);
  const usageQuery = useKnowledgeUsage(20);
  return (
    <section className="km-two-column">
      <div className="km-card km-query-panel">
        <span className="km-eyebrow">Preflight</span>
        <h2>Scope and context risk</h2>
        <textarea
          value={task}
          onChange={(event) => onTaskChange(event.target.value)}
          rows={5}
          placeholder="Describe the implementation task to scope"
        />
        {preflightQuery.data !== undefined ? (
          <div className="km-card km-preflight-card">
            <header>
              <strong>Scope {preflightQuery.data.report.scope}</strong>
              <StatePill
                variant={preflightQuery.data.report.risk_flags.length > 0 ? "degraded" : "ok"}
                label={`${preflightQuery.data.report.recommended_budget} context`}
              />
            </header>
            <span className="km-preflight-card__index">
              Index: {preflightQuery.data.report.index_state}
            </span>
            <div className="km-preflight-card__signals">
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
        <CardRefreshFooter>
          <RefreshButton
            label="preflight"
            onRefresh={() => void preflightQuery.refetch()}
            isFetching={preflightQuery.isFetching}
          />
        </CardRefreshFooter>
      </div>
      <div className="km-card km-usage-ledger">
        <header>
          <span className="km-eyebrow">Usage ledger</span>
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
        <CardRefreshFooter>
          <RefreshButton
            label="usage ledger"
            onRefresh={() => void usageQuery.refetch()}
            isFetching={usageQuery.isFetching}
          />
        </CardRefreshFooter>
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
