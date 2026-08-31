import type { ProviderState } from "@/api/projectLifecycle";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { RefreshButton } from "@/components/RefreshButton";

type ProviderAccount = ProviderState["accounts"][number];

export interface GitHubAccountPanelProps {
  state: ProviderState | undefined;
  isPending: boolean;
  error: string | null;
  switchBusy: boolean;
  onSwitch: (user: string, host: string) => void;
  onRefresh: () => void;
  isFetching: boolean;
}

export function GitHubAccountPanel({
  state,
  isPending,
  error,
  switchBusy,
  onSwitch,
  onRefresh,
  isFetching,
}: GitHubAccountPanelProps) {
  const accounts = state?.accounts ?? [];
  const activeAccount = accounts.find((account) => account.active);
  const secondaryAccounts = accounts.filter((account) => !account.active);

  return (
    <section className="overview-github-panel" aria-label="GitHub accounts on this computer">
      <header className="overview-github-panel__header">
        <strong>GitHub</strong>
      </header>

      <div className="overview-github-panel__body">
        {isPending ? (
          <p className="overview-github-panel__message">Checking GitHub accounts…</p>
        ) : error !== null ? (
          <p className="overview-github-panel__message overview-github-panel__message--error">
            GitHub status is unavailable: {error}
          </p>
        ) : accounts.length === 0 ? (
          <div className="overview-github-panel__empty">
            <span className="overview-github-account__icon" data-health="unhealthy">
              <GitHubIcon />
            </span>
            <span>
              <b>No GitHub user</b>
              <small>Sign in with GitHub CLI to connect this computer.</small>
            </span>
          </div>
        ) : (
          <div className="overview-github-panel__accounts">
            {activeAccount !== undefined ? (
              <AccountIdentity
                account={activeAccount}
                authenticated={state?.authenticated === true}
              />
            ) : null}

            {secondaryAccounts.map((account) => (
              <div
                key={`${account.host}:${account.user}`}
                className="overview-github-panel__switch-target"
              >
                {activeAccount !== undefined ? (
                  <button
                    type="button"
                    className="overview-github-panel__swap"
                    aria-label={`Swap to ${account.user}`}
                    title={
                      account.valid ? `Make ${account.user} active` : `${account.user} is invalid`
                    }
                    disabled={switchBusy || !account.valid}
                    onClick={() => onSwitch(account.user, account.host)}
                  >
                    <ArrowIcon />
                    <span>{switchBusy ? "Switching…" : "Swap"}</span>
                  </button>
                ) : null}
                <AccountIdentity account={account} authenticated={state?.authenticated === true} />
              </div>
            ))}
          </div>
        )}
      </div>
      <CardRefreshFooter>
        <RefreshButton label="GitHub account" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </section>
  );
}

function AccountIdentity({
  account,
  authenticated,
}: {
  account: ProviderAccount;
  authenticated: boolean;
}) {
  const healthy = authenticated && account.valid && account.active;
  const status = healthy
    ? "logged in, valid, and active"
    : !account.valid
      ? "invalid"
      : account.active
        ? "not logged in"
        : "inactive";

  return (
    <article className="overview-github-account" data-active={account.active}>
      <span
        className="overview-github-account__icon"
        data-health={healthy ? "healthy" : "unhealthy"}
        role="img"
        aria-label={`${account.user} is ${status}`}
      >
        <GitHubIcon />
      </span>
      <b>{account.user}</b>
      <small>
        {account.host} · {account.active ? "active" : account.valid ? "available" : "invalid"}
      </small>
    </article>
  );
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.87c-2.78.6-3.37-1.18-3.37-1.18-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.35 1.09 2.92.83.09-.65.35-1.09.64-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.56 9.56 0 0 1 12 6.82a9.5 9.5 0 0 1 2.5.34c1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.86v2.76c0 .27.18.58.69.48A10 10 0 0 0 12 2Z"
      />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h14m-6-6 6 6-6 6" />
    </svg>
  );
}
