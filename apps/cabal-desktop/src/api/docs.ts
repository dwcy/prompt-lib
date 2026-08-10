// Typed API hooks for the Docs reference module: README summary + docs/ markdown listing.
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { useProjectContextStore } from "@/stores/projectContext";

export const readmeSummarySchema = z.object({
  path: z.string(),
  title: z.string(),
  line_count: z.number(),
  content: z.string(),
});

export const docEntrySchema = z.object({
  name: z.string(),
  path: z.string(),
  description: z.string(),
});

export const docsPayloadSchema = z.object({
  readme: readmeSummarySchema.nullable(),
  documents: z.array(docEntrySchema),
});

export const docContentPayloadSchema = z.object({
  path: z.string(),
  content: z.string(),
});

export type DocsPayload = z.infer<typeof docsPayloadSchema>;

export function useDocs() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped("docs", projectPath),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/docs", docsPayloadSchema, signal);
      return requireData(envelope, "docs");
    },
    enabled: projectPath !== null,
  });
}

export function useDocContent(path: string | null) {
  return useQuery({
    queryKey: queryKeys.global("docs", "content", path ?? ""),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/docs/content?path=${encodeURIComponent(path ?? "")}`,
        docContentPayloadSchema,
        signal,
      );
      return requireData(envelope, "docs");
    },
    enabled: path !== null,
  });
}
