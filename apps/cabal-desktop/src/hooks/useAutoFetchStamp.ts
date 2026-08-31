// Timestamp of the oldest self-polling query in the cache — the moment from which every
// auto-refreshing data source is known-good. Queries without a refetchInterval are excluded:
// they only refetch on mount, window focus, or their card's own refresh button, so folding them
// in would make the stamp report a freshness the auto-polled data does not have.
import type { Query } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useSyncExternalStore } from "react";

// refetchInterval is an observer option, not a query option, so the polling flag lives on whoever
// is currently subscribed to the query rather than on the cache entry itself.
function isPolling(query: Query): boolean {
  return query.observers.some((observer) => Boolean(observer.options.refetchInterval));
}

export function useAutoFetchStamp(): number | null {
  const queryClient = useQueryClient();

  const subscribe = useCallback(
    (onChange: () => void) => queryClient.getQueryCache().subscribe(onChange),
    [queryClient],
  );

  const getSnapshot = useCallback(() => {
    const stamps = queryClient
      .getQueryCache()
      .getAll()
      .filter((query) => isPolling(query) && query.state.dataUpdatedAt > 0)
      .map((query) => query.state.dataUpdatedAt);
    return stamps.length === 0 ? null : Math.min(...stamps);
  }, [queryClient]);

  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
