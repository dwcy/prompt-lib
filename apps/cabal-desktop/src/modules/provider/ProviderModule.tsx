// GitHub provider console screen: repo/org header stats, CLI accounts + device-login table, and
// a repo browser + clone runway in place of the mock's CI/PR panels (the gh CLI payload carries
// no workflow-run or pull-request data) — per the cabal-console mock's isGithub section.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useJob } from "@/api/jobs";
import { useProjectContext } from "@/api/project";
import { type ProviderRepo, useProviderRepos, useProviderState } from "@/api/projectLifecycle";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { useAction } from "@/hooks/useAction";
import { ProviderAccountsCard } from "@/modules/provider/components/ProviderAccountsCard";
import { ProviderClonePanel } from "@/modules/provider/components/ProviderClonePanel";
import { ProviderHeaderCard } from "@/modules/provider/components/ProviderHeaderCard";
import { ProviderRepoListCard } from "@/modules/provider/components/ProviderRepoListCard";
import "./ProviderModule.css";

const DEFAULT_PARENT = "C:\\projects";
const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

export function ProviderModule() {
  const queryClient = useQueryClient();
  const providerQuery = useProviderState();
  const projectQuery = useProjectContext();
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

  const projectName = projectQuery.data?.is_git_repo === true ? projectQuery.data.name : null;

  return (
    <div className="provider-console">
      {providerQuery.isPending ? (
        <EmptyState title="Checking GitHub CLI..." />
      ) : providerQuery.isError ? (
        <EmptyState title="Provider status failed" body={providerQuery.error.message} />
      ) : (
        <>
          <ProviderHeaderCard
            projectName={projectName}
            ghStatus={providerQuery.data.gh_status}
            accountsCount={providerQuery.data.accounts.length}
            reposCount={reposQuery.data?.count ?? null}
            authenticated={providerQuery.data.authenticated}
          />
          <ProviderAccountsCard
            accounts={providerQuery.data.accounts}
            login={providerQuery.data.login}
            loginPhase={loginAction.phase}
            loginJobId={loginAction.jobId}
            copyState={copyState}
            verificationUri={verificationUri}
            onAddAccount={startLogin}
            onCopyDeviceCode={() => void copyDeviceCode()}
            onSwitch={(user, host) => switchAction.prepare({ user, host })}
            onForget={(user, host) => forgetAction.prepare({ user, host })}
          />
        </>
      )}

      <div className="provider-console__repos-row">
        <ProviderRepoListCard
          repos={visibleRepos}
          totalCount={reposQuery.data?.count ?? visibleRepos.length}
          queryText={repoQueryText}
          onQueryChange={setRepoQueryText}
          selectedRepo={selectedRepo}
          onSelectRepo={setSelectedRepo}
          isPending={reposQuery.isPending}
          isError={reposQuery.isError}
          error={reposQuery.error ?? null}
        />
        <ProviderClonePanel
          selectedRepo={selectedRepo}
          destination={destination}
          onDestinationChange={setDestination}
          onClone={startClone}
          clonePhase={cloneAction.phase}
          cloneJobId={cloneAction.jobId}
        />
      </div>

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
