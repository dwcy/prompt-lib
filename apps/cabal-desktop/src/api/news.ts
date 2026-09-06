import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, requireData } from "@/api/client";
import { newsItemStateSchema, newsPayloadSchema, newsSourcesPayloadSchema, type NewsPayload } from "@/api/schemas";

export function useNewsFeed() {
  return useQuery({
    queryKey: ["news-feed"],
    queryFn: async ({ signal }) => requireData(await apiGet("/api/news/items", newsPayloadSchema, signal), "news feed"),
    staleTime: 60_000,
  });
}

export function useRefreshNews() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => requireData(await apiPost<NewsPayload>("/api/news/refresh", newsPayloadSchema), "news refresh"),
    onSuccess: (data) => client.setQueryData(["news-feed"], data),
  });
}

export function useNewsItemState() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, read, saved }: { id: string; read?: boolean; saved?: boolean }) =>
      requireData(await apiPost(`/api/news/items/${id}/state`, newsItemStateSchema, { read, saved }), "news item state"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["news-feed"] }),
  });
}

export function useNewsSourceState() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) =>
      requireData(await apiPost(`/api/news/sources/${id}/state`, newsSourcesPayloadSchema, { enabled }), "news source state"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["news-feed"] }),
  });
}
