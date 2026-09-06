// Repo/org identity header: project name (when known) + gh CLI status, plus real account/repo
// counts and auth state as right-aligned mono stat pairs — the console mock's isGithub header row.
export interface ProviderHeaderCardProps {
  projectName: string | null;
  ghStatus: string;
  accountsCount: number;
  reposCount: number | null;
  authenticated: boolean;
}

export function ProviderHeaderCard({
  projectName,
  ghStatus,
  accountsCount,
  reposCount,
  authenticated,
}: ProviderHeaderCardProps) {
  return (
    <section className="provider-header-card">
      <div className="provider-header-card__identity">
        <strong className="select-none">{projectName ?? "GitHub provider"}</strong>
        <span className="provider-header-card__subline">via GitHub CLI &middot; {ghStatus}</span>
      </div>
      <div className="provider-header-card__stats select-none">
        <span>
          <strong>{accountsCount}</strong> accounts
        </span>
        <span>
          <strong>{reposCount ?? "—"}</strong> repos
        </span>
        <span
          className={
            authenticated ? "provider-header-card__stat--ok" : "provider-header-card__stat--warning"
          }
        >
          <strong>{authenticated ? "✓" : "✕"}</strong>{" "}
          {authenticated ? "authenticated" : "not authenticated"}
        </span>
      </div>
    </section>
  );
}
