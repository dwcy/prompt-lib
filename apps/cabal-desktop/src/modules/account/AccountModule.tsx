import { useAccount, useClaudeInfo } from "@/api/observability";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";

export function AccountModule() {
  const accountQuery = useAccount();
  const infoQuery = useClaudeInfo();

  if (accountQuery.isPending || infoQuery.isPending) {
    return <EmptyState title="Loading account and assistant info…" />;
  }

  if (accountQuery.isError) {
    return <EmptyState title="Could not load account state" body={accountQuery.error.message} />;
  }

  if (infoQuery.isError) {
    return <EmptyState title="Could not load assistant info" body={infoQuery.error.message} />;
  }

  const account = accountQuery.data;
  const info = infoQuery.data;
  const credentialCount = account.credential_sources.filter((source) => source.present).length;
  const documentCount = info.documents.filter((doc) => doc.present).length;
  const runtimeEntries = Object.entries(info.runtime);

  return (
    <div className="account-vault">
      <section className="observability-hero">
        <div>
          <span className="us3-eyebrow">Identity vault</span>
          <h1>{account.identity ?? "No Claude account detected"}</h1>
          <p>
            Credential presence and loaded instruction sources are shown without exposing secret
            values.
          </p>
        </div>
        <StatePill
          variant={account.authenticated ? "ok" : "missing"}
          label={account.authenticated ? "signed in" : "missing"}
        />
        <div className="account-vault__metrics">
          <span>
            <strong>{credentialCount}</strong>
            <small>credential sources</small>
          </span>
          <span>
            <strong>{documentCount}</strong>
            <small>instruction layers</small>
          </span>
          <span>
            <strong>{runtimeEntries.length}</strong>
            <small>runtime facts</small>
          </span>
        </div>
      </section>

      <section className="account-vault__grid">
        <div className="account-vault__panel">
          <header className="account-vault__panel-header">
            <div>
              <span className="us3-eyebrow">Presence only</span>
              <h2>Credential chain</h2>
            </div>
            <span>
              {credentialCount}/{account.credential_sources.length}
            </span>
          </header>
          <div className="credential-stack">
            {account.credential_sources.map((source, index) => (
              <div key={source.path} className="credential-row">
                <span className="credential-row__step">{String(index + 1).padStart(2, "0")}</span>
                <span>
                  <strong>{source.label}</strong>
                  <small>{source.path}</small>
                </span>
                <StatePill variant={source.present ? "ok" : "missing"} label={source.value_state} />
              </div>
            ))}
          </div>
        </div>

        <div className="account-vault__panel account-vault__panel--wide">
          <header className="account-vault__panel-header">
            <div>
              <span className="us3-eyebrow">Load order</span>
              <h2>Instruction stack</h2>
            </div>
            <span>
              {documentCount}/{info.documents.length}
            </span>
          </header>
          <div className="instruction-stack">
            {info.documents.map((doc, index) => (
              <article key={doc.label} className="instruction-card">
                <header>
                  <span className="instruction-card__identity">
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{doc.label}</strong>
                  </span>
                  <StatePill
                    variant={doc.present ? "ok" : "unavailable"}
                    label={doc.present ? `${doc.line_count} lines` : "missing"}
                  />
                </header>
                <small>{doc.path}</small>
                <pre>{doc.preview || "No preview available."}</pre>
              </article>
            ))}
          </div>
        </div>

        <div className="account-vault__panel account-runtime-panel">
          <header className="account-vault__panel-header">
            <div>
              <span className="us3-eyebrow">Execution context</span>
              <h2>Runtime provenance</h2>
            </div>
          </header>
          {runtimeEntries.length === 0 ? (
            <p className="account-runtime-panel__empty">No runtime facts reported.</p>
          ) : (
            <dl className="account-runtime-grid">
              {runtimeEntries.map(([key, value]) => (
                <div key={key}>
                  <dt>{humanizeRuntimeKey(key)}</dt>
                  <dd>{displayRuntimeValue(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>
    </div>
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
