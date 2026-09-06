// "CLI accounts" card: gh auth status rows (avatar chip, identity, storage, validity, active,
// switch/forget), the "+ Add account" trigger for the device-login flow, and its live device
// code banner — the console mock's account table, adapted to the real gh_accounts payload.
import type { ProviderState } from "@/api/projectLifecycle";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { RefreshButton } from "@/components/RefreshButton";
import { StatePill } from "@/components/StatePill";
import type { ActionPhase } from "@/hooks/useAction";

type ProviderAccount = ProviderState["accounts"][number];
type ProviderLogin = ProviderState["login"];

export interface ProviderAccountsCardProps {
  accounts: ProviderAccount[];
  login: ProviderLogin;
  loginPhase: ActionPhase;
  loginJobId: string | null;
  copyState: "idle" | "copied" | "failed";
  verificationUri: string;
  onAddAccount: () => void;
  onCopyDeviceCode: () => void;
  onSwitch: (user: string, host: string) => void;
  onForget: (user: string, host: string) => void;
  onRefresh: () => void;
  isFetching: boolean;
}

export function ProviderAccountsCard({
  accounts,
  login,
  loginPhase,
  loginJobId,
  copyState,
  verificationUri,
  onAddAccount,
  onCopyDeviceCode,
  onSwitch,
  onForget,
  onRefresh,
  isFetching,
}: ProviderAccountsCardProps) {
  const addAccountBusy = loginPhase === "preparing" || loginPhase === "executing";

  return (
    <section className="provider-accounts-card">
      <header className="provider-accounts-card__header">
        <div>
          <strong className="select-none">CLI accounts</strong>
          <span className="provider-accounts-card__subtitle select-none">gh auth status</span>
        </div>
        <button
          type="button"
          className="provider-accounts-card__add"
          onClick={onAddAccount}
          disabled={addAccountBusy}
        >
          {addAccountBusy ? "Preparing…" : "+ Add account"}
        </button>
      </header>

      {login.user_code !== undefined && login.user_code.length > 0 ? (
        <div className="provider-device-banner">
          <span className="provider-device-banner__field">
            <small>Device code</small>
            <strong>{login.user_code}</strong>
            <button type="button" onClick={onCopyDeviceCode}>
              {copyState === "copied"
                ? "Copied"
                : copyState === "failed"
                  ? "Copy failed"
                  : "Copy code"}
            </button>
          </span>
          <span className="provider-device-banner__field">
            <small>Verification</small>
            <a href={normalizeExternalUrl(verificationUri)} target="_blank" rel="noreferrer">
              {verificationUri}
            </a>
          </span>
          <StatePill variant="connecting" label={login.state} />
        </div>
      ) : null}

      {accounts.length === 0 ? (
        <EmptyState
          title="No GitHub accounts detected"
          body="GitHub CLI has no stored account for this machine."
        />
      ) : (
        <div className="provider-accounts-card__rows">
          {accounts.map((account) => (
            <article
              key={`${account.host}:${account.user}`}
              className="provider-accounts-card__row"
            >
              <span className="provider-accounts-card__avatar" aria-hidden="true">
                {initialsFromLogin(account.user)}
              </span>
              <span className="provider-accounts-card__identity">
                <strong>{account.user}</strong>
                <small>{account.host}</small>
              </span>
              <code className="provider-accounts-card__storage">
                {account.storage || "credential store"}
              </code>
              <span className="provider-accounts-card__validity">
                <StatePill
                  variant={account.valid ? "ok" : "failed"}
                  label={account.valid ? "valid" : "invalid"}
                />
              </span>
              <span className="provider-accounts-card__active">
                <StatePill
                  variant={account.active ? "ok" : "unavailable"}
                  label={account.active ? "active" : "inactive"}
                />
              </span>
              <span className="provider-accounts-card__actions">
                {!account.active ? (
                  <button
                    type="button"
                    onClick={() => onSwitch(account.user, account.host)}
                    disabled={!account.valid}
                  >
                    Switch to
                  </button>
                ) : null}
                <button
                  type="button"
                  className="danger-button"
                  onClick={() => onForget(account.user, account.host)}
                >
                  Forget
                </button>
              </span>
            </article>
          ))}
        </div>
      )}
      <p className="provider-accounts-card__footer select-none">
        Switching or forgetting an account updates the active gh credential immediately.
      </p>
      {loginJobId !== null ? <JobPane jobId={loginJobId} /> : null}
      <CardRefreshFooter>
        <RefreshButton label="accounts" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </section>
  );
}

function initialsFromLogin(user: string): string {
  const clean = user.replace(/[^a-zA-Z0-9]/g, "");
  return clean.length > 0 ? clean.slice(0, 2).toUpperCase() : "?";
}

function normalizeExternalUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}
