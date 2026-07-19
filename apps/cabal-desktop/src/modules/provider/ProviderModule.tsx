import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useJob } from "@/api/jobs";
import { type ProviderRepo, useProviderRepos, useProviderState } from "@/api/projectLifecycle";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";

const DEFAULT_PARENT = "C:\\projects";
const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

export function ProviderModule() {
  const queryClient = useQueryClient();
  const providerQuery = useProviderState();
  const [repoQueryText, setRepoQueryText] = useState("");
  const reposQuery = useProviderRepos(repoQueryText);
  const [selectedRepo, setSelectedRepo] = useState<ProviderRepo | null>(null);
  const [destination, setDestination] = useState("");
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const loginAction = useAction("provider.login");
  const switchAction = useAction("provider.switch_account");
  const forgetAction = useAction("provider.forget_account");
  const cloneAction = useAction("provider.clone");
  const verificationUri =
    providerQuery.data?.login.verification_uri ?? "https://github.com/login/device";

  const repos = reposQuery.data?.repos ?? [];
  const visibleRepos = useMemo(() => repos.slice(0, 80), [repos]);
  const loginJob = useJob(loginAction.jobId ?? "", {
    enabled: loginAction.jobId !== null,
    refetchInterval: 1_000,
  });
  const cloneJob = useJob(cloneAction.jobId ?? "", {
    enabled: cloneAction.jobId !== null,
    refetchInterval: 1_000,
  });

  useEffect(() => {
    if (selectedRepo === null && repos.length > 0) setSelectedRepo(repos[0]);
  }, [repos, selectedRepo]);

  useEffect(() => {
    if (selectedRepo === null) return;
    setDestination(`${DEFAULT_PARENT}\\${selectedRepo.name}`);
  }, [selectedRepo]);

  useEffect(() => {
    if (loginJob.data === undefined || !TERMINAL_STATES.has(loginJob.data.state)) return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("provider", "state") });
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("provider", "repos") });
  }, [loginJob.data, queryClient]);

  useEffect(() => {
    if (cloneJob.data === undefined || cloneJob.data.state !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.project.current() });
  }, [cloneJob.data, queryClient]);

  useEffect(() => {
    if (switchAction.phase !== "succeeded" && forgetAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("provider", "state") });
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("provider", "repos") });
  }, [forgetAction.phase, queryClient, switchAction.phase]);

  function startLogin(): void {
    setCopyState("idle");
    loginAction.prepare({ scopes: ["repo", "read:org"] });
  }

  function startClone(): void {
    if (selectedRepo === null || destination.trim().length === 0) return;
    cloneAction.prepare({
      repo: selectedRepo.full_name,
      destination: destination.trim(),
      switch_to_project: true,
    });
  }

  async function copyDeviceCode(): Promise<void> {
    const code = providerQuery.data?.login.user_code;
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  return (
    <div className="provider-workbench">
      <section className="provider-auth-panel">
        <div className="module-section-heading">
          <span className="module-eyebrow select-none">GitHub provider</span>
          <h2>Accounts and device login</h2>
        </div>
        {providerQuery.isPending ? (
          <EmptyState title="Checking GitHub CLI..." />
        ) : providerQuery.isError ? (
          <EmptyState title="Provider status failed" body={providerQuery.error.message} />
        ) : (
          <>
            <div className="provider-auth-panel__status">
              <StatePill
                variant={providerQuery.data.authenticated ? "ok" : "unavailable"}
                label={providerQuery.data.authenticated ? "authenticated" : "login needed"}
              />
              <span>{providerQuery.data.gh_status}</span>
            </div>
            <div className="provider-account-stack">
              {providerQuery.data.accounts.length === 0 ? (
                <EmptyState
                  title="No GitHub accounts detected"
                  body="GitHub CLI has no stored account for this machine."
                />
              ) : (
                providerQuery.data.accounts.map((account, index) => (
                  <article
                    key={`${account.host}:${account.user}`}
                    className={`provider-account-card${
                      account.active ? " provider-account-card--active" : ""
                    }`}
                  >
                    <span className="provider-account-card__index">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="provider-account-card__identity">
                      <strong>{account.user}</strong>
                      <small>{account.host}</small>
                    </span>
                    <StatePill
                      variant={account.valid ? "ok" : "failed"}
                      label={account.active ? "active" : account.valid ? "valid" : "invalid"}
                    />
                    <code>{account.storage || "credential store"}</code>
                    <span className="provider-account-card__actions">
                      {!account.active ? (
                        <button
                          type="button"
                          onClick={() =>
                            switchAction.prepare({ user: account.user, host: account.host })
                          }
                          disabled={!account.valid}
                        >
                          Make active
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="danger-button"
                        onClick={() =>
                          forgetAction.prepare({ user: account.user, host: account.host })
                        }
                      >
                        Forget
                      </button>
                    </span>
                  </article>
                ))
              )}
            </div>
            {providerQuery.data.login.user_code ? (
              <div className="provider-device-code">
                <span>
                  <small>Device code</small>
                  <strong>{providerQuery.data.login.user_code}</strong>
                  <button type="button" onClick={() => void copyDeviceCode()}>
                    {copyState === "copied"
                      ? "Copied"
                      : copyState === "failed"
                        ? "Copy failed"
                        : "Copy code"}
                  </button>
                </span>
                <span>
                  <small>Verification</small>
                  <a href={normalizeExternalUrl(verificationUri)} target="_blank" rel="noreferrer">
                    {verificationUri}
                  </a>
                </span>
                <StatePill variant="connecting" label={providerQuery.data.login.state} />
              </div>
            ) : null}
            <button
              type="button"
              className="provider-primary-action"
              onClick={startLogin}
              disabled={loginAction.phase === "preparing" || loginAction.phase === "executing"}
            >
              {loginAction.phase === "preparing"
                ? "Preparing code..."
                : loginAction.phase === "executing"
                  ? "Starting login..."
                  : "Start device login"}
            </button>
            {loginAction.jobId !== null ? <JobPane jobId={loginAction.jobId} /> : null}
          </>
        )}
      </section>

      <section className="provider-repo-panel">
        <div className="provider-repo-panel__toolbar">
          <div className="module-section-heading">
            <span className="module-eyebrow select-none">Clone source</span>
            <h2>Repositories</h2>
          </div>
          <input
            type="search"
            aria-label="Filter repositories"
            value={repoQueryText}
            onChange={(event) => setRepoQueryText(event.target.value)}
            placeholder="Filter owner/name or description"
            autoComplete="off"
            spellCheck={false}
          />
          {reposQuery.data !== undefined ? (
            <span className="provider-repo-panel__count select-none">
              {visibleRepos.length}
              {repos.length > visibleRepos.length ? ` of ${repos.length}` : ""}
            </span>
          ) : null}
        </div>
        {reposQuery.isPending ? (
          <EmptyState title="Loading repositories..." />
        ) : reposQuery.isError ? (
          <EmptyState title="Repository list unavailable" body={reposQuery.error.message} />
        ) : visibleRepos.length === 0 ? (
          <EmptyState title="No repositories matched" />
        ) : (
          <div className="provider-repo-grid">
            {visibleRepos.map((repo) => (
              <button
                type="button"
                key={repo.full_name}
                className={`provider-repo-card${
                  selectedRepo?.full_name === repo.full_name ? " provider-repo-card--selected" : ""
                }`}
                aria-pressed={selectedRepo?.full_name === repo.full_name}
                onClick={() => setSelectedRepo(repo)}
              >
                <span className="provider-repo-card__name">{repo.full_name}</span>
                <span className="provider-repo-card__meta">
                  {repo.visibility} / {formatDate(repo.updated_at)}
                </span>
                <span className="provider-repo-card__description">
                  {repo.description || "No description"}
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="provider-clone-panel">
        <div className="module-section-heading">
          <span className="module-eyebrow select-none">Clone runway</span>
          <h2>{selectedRepo?.full_name ?? "Select a repository"}</h2>
        </div>
        <ol className="provider-clone-runway" aria-label="Clone and switch workflow">
          <li className={selectedRepo === null ? "" : "is-ready"}>
            <span>01</span>
            <div>
              <small>Source</small>
              <strong>{selectedRepo?.full_name ?? "Select a repository"}</strong>
              <p>{selectedRepo?.url ?? "Repository metadata will appear here."}</p>
            </div>
          </li>
          <li className={destination.trim().length === 0 ? "" : "is-ready"}>
            <span>02</span>
            <label className="provider-field">
              <small>Destination</small>
              <input
                type="text"
                value={destination}
                onChange={(event) => setDestination(event.target.value)}
                autoComplete="off"
                spellCheck={false}
                placeholder="C:\\projects\\repo"
              />
            </label>
          </li>
          <li className={selectedRepo !== null && destination.trim().length > 0 ? "is-ready" : ""}>
            <span>03</span>
            <div>
              <small>Workspace handoff</small>
              <strong>Clone, register, and switch context</strong>
              <p>The new checkout becomes the active Cabal project after the job succeeds.</p>
            </div>
          </li>
        </ol>
        <button
          type="button"
          className="provider-primary-action"
          onClick={startClone}
          disabled={
            selectedRepo === null ||
            destination.trim().length === 0 ||
            cloneAction.phase === "preparing" ||
            cloneAction.phase === "executing"
          }
        >
          {cloneAction.phase === "preparing"
            ? "Preparing clone..."
            : cloneAction.phase === "executing"
              ? "Starting clone..."
              : "Clone and switch workspace"}
        </button>
        {cloneAction.jobId !== null ? <JobPane jobId={cloneAction.jobId} /> : null}
      </section>

      <ConfirmDialog
        isOpen={loginAction.phase !== "idle" && loginAction.phase !== "succeeded"}
        actionTitle="Authorize GitHub provider"
        ticket={loginAction.ticket}
        phase={loginAction.phase}
        reviewNotice={loginAction.reviewNotice}
        error={loginAction.error}
        onConfirm={loginAction.confirm}
        onCancel={loginAction.reset}
      />
      <ConfirmDialog
        isOpen={switchAction.phase !== "idle" && switchAction.phase !== "succeeded"}
        actionTitle="Switch GitHub account"
        ticket={switchAction.ticket}
        phase={switchAction.phase}
        reviewNotice={switchAction.reviewNotice}
        error={switchAction.error}
        onConfirm={switchAction.confirm}
        onCancel={switchAction.reset}
      />
      <ConfirmDialog
        isOpen={forgetAction.phase !== "idle" && forgetAction.phase !== "succeeded"}
        actionTitle="Forget GitHub account"
        ticket={forgetAction.ticket}
        phase={forgetAction.phase}
        reviewNotice={forgetAction.reviewNotice}
        error={forgetAction.error}
        onConfirm={forgetAction.confirm}
        onCancel={forgetAction.reset}
      />
      <ConfirmDialog
        isOpen={cloneAction.phase !== "idle" && cloneAction.phase !== "succeeded"}
        actionTitle="Clone repository"
        ticket={cloneAction.ticket}
        phase={cloneAction.phase}
        reviewNotice={cloneAction.reviewNotice}
        error={cloneAction.error}
        onConfirm={cloneAction.confirm}
        onCancel={cloneAction.reset}
      />
    </div>
  );
}

function formatDate(value: string): string {
  if (value.trim().length === 0) return "unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function normalizeExternalUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}
