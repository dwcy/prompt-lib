// Repo browser card: filter input + selectable repo rows, restyled in the console's card/table
// language. Replaces the mock's "workflow runs" panel — the provider payload has no CI/PR data.
import type { ProviderRepo } from "@/api/projectLifecycle";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";

export interface ProviderRepoListCardProps {
  repos: ProviderRepo[];
  totalCount: number;
  queryText: string;
  onQueryChange: (value: string) => void;
  selectedRepo: ProviderRepo | null;
  onSelectRepo: (repo: ProviderRepo) => void;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  onRefresh: () => void;
  isFetching: boolean;
}

export function ProviderRepoListCard({
  repos,
  totalCount,
  queryText,
  onQueryChange,
  selectedRepo,
  onSelectRepo,
  isPending,
  isError,
  error,
  onRefresh,
  isFetching,
}: ProviderRepoListCardProps) {
  return (
    <section className="provider-repo-list-card">
      <header className="provider-repo-list-card__header">
        <strong className="select-none">Repositories</strong>
        <input
          type="search"
          aria-label="Filter repositories"
          value={queryText}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Filter owner/name or description"
          autoComplete="off"
          spellCheck={false}
        />
        {!isPending && !isError ? (
          <span className="provider-repo-list-card__count select-none">
            {repos.length}
            {totalCount > repos.length ? ` of ${totalCount}` : ""}
          </span>
        ) : null}
      </header>
      {isPending ? (
        <EmptyState title="Loading repositories…" />
      ) : isError ? (
        <EmptyState title="Repository list unavailable" body={error?.message} />
      ) : repos.length === 0 ? (
        <EmptyState title="No repositories matched" />
      ) : (
        <div className="provider-repo-list-card__rows">
          {repos.map((repo) => (
            <button
              type="button"
              key={repo.full_name}
              className={`provider-repo-list-card__row${
                selectedRepo?.full_name === repo.full_name
                  ? " provider-repo-list-card__row--selected"
                  : ""
              }`}
              aria-pressed={selectedRepo?.full_name === repo.full_name}
              onClick={() => onSelectRepo(repo)}
            >
              <span className="provider-repo-list-card__name">{repo.full_name}</span>
              <span className="provider-repo-list-card__meta">
                {repo.visibility} &middot; {formatDate(repo.updated_at)}
              </span>
              <span className="provider-repo-list-card__description">
                {repo.description || "No description"}
              </span>
            </button>
          ))}
        </div>
      )}
      <CardRefreshFooter>
        <RefreshButton label="repositories" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </section>
  );
}

function formatDate(value: string): string {
  if (value.trim().length === 0) return "unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
