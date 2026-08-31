// Icon-only refresh control for a card that owns a query; spins while that query is fetching.
// Rendered inside `.card-refresh-footer` so it lands in the card's bottom-right corner.
export interface RefreshButtonProps {
  /** What this button refreshes, e.g. "Git" — used to build the accessible label. */
  label: string;
  onRefresh: () => void;
  isFetching?: boolean;
}

export function RefreshButton({ label, onRefresh, isFetching = false }: RefreshButtonProps) {
  const description = isFetching ? `Refreshing ${label}…` : `Refresh ${label}`;
  return (
    <button
      type="button"
      className="refresh-button"
      onClick={onRefresh}
      disabled={isFetching}
      aria-label={description}
      title={description}
      data-refreshing={isFetching ? "true" : undefined}
    >
      <svg
        className="refresh-button__icon"
        viewBox="0 0 24 24"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
        <path d="M21 3v5h-5" />
        <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
        <path d="M3 21v-5h5" />
      </svg>
    </button>
  );
}
