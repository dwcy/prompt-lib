// Claude account card: identity + credential presence facts, runtime provenance, and quick actions
// linking to a manual info refresh and the Models module.
import type { AccountPayload } from "@/api/observability";

export interface ClaudeAccountCardProps {
  account: AccountPayload;
  runtime: Record<string, unknown>;
  isRefreshing: boolean;
  onRefresh: () => void;
  onOpenModels: () => void;
}

export function ClaudeAccountCard({
  account,
  runtime,
  isRefreshing,
  onRefresh,
  onOpenModels,
}: ClaudeAccountCardProps) {
  const runtimeEntries = Object.entries(runtime);

  return (
    <section className="ccfg-account-card">
      <header className="ccfg-account-card__header">
        <b>Claude account</b>
        <span
          className={`ccfg-status-badge ${account.authenticated ? "ccfg-tone-ok" : "ccfg-tone-warning"}`}
        >
          ● {account.authenticated ? "token present" : "not authenticated"}
        </span>
      </header>

      <div className="ccfg-fact-rows">
        <div className="ccfg-fact-row">
          <span className="ccfg-fact-row__label">signed in</span>
          <span className="ccfg-fact-row__value ccfg-mono">
            {account.identity ?? "not signed in"}
          </span>
        </div>
        {account.credential_sources.map((source) => (
          <div key={source.path} className="ccfg-fact-row">
            <span className="ccfg-fact-row__label">{source.label}</span>
            <span
              className={`ccfg-fact-row__value ccfg-mono ${source.present ? "ccfg-tone-ok" : "ccfg-tone-warning"}`}
            >
              {source.present ? "✓" : "✕"} {source.value_state}
            </span>
          </div>
        ))}
      </div>

      <div className="ccfg-account-card__actions">
        <button
          type="button"
          className="ccfg-btn ccfg-btn--accent select-none"
          onClick={onRefresh}
          disabled={isRefreshing}
        >
          {isRefreshing ? "Refreshing…" : "Claude info"}
        </button>
        <button type="button" className="ccfg-btn select-none" onClick={onOpenModels}>
          Models
        </button>
      </div>

      {runtimeEntries.length > 0 ? (
        <div className="ccfg-runtime">
          <span className="ccfg-runtime__eyebrow select-none">Runtime</span>
          <dl className="ccfg-runtime__grid">
            {runtimeEntries.map(([key, value]) => (
              <div key={key}>
                <dt>{humanizeRuntimeKey(key)}</dt>
                <dd>{displayRuntimeValue(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </section>
  );
}

function humanizeRuntimeKey(value: string) {
  return value.replaceAll("_", " ");
}

function displayRuntimeValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "not reported";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
