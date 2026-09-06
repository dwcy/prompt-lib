import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";

export const knowledgeCountsSchema = z.object({
  nodes: z.number(),
  edges: z.number(),
  by_type: z.record(z.string(), z.number()),
  by_relation: z.record(z.string(), z.number()),
  findings_by_severity: z.record(z.string(), z.number()),
});

export const knowledgeSummarySchema = z.object({
  available: z.boolean(),
  repo_root: z.string(),
  bundle_root: z.string(),
  index_path: z.string(),
  usage_path: z.string(),
  generated_at: z.string().nullable(),
  index_available: z.boolean(),
  semantic_available: z.boolean(),
  usage_count: z.number(),
  counts: knowledgeCountsSchema,
  digest: z.string(),
});

export const knowledgeNodeSchema = z.object({
  id: z.string(),
  type: z.string(),
  label: z.string(),
  resource: z.string(),
  doc: z.string(),
  tags: z.array(z.string()),
  metrics: z.record(z.string(), z.unknown()),
});

export const knowledgeEvidenceSchema = z.record(z.string(), z.unknown());

export const knowledgeEdgeSchema = z.object({
  id: z.string(),
  from: z.string(),
  to: z.string(),
  target_ref: z.string(),
  relation: z.string(),
  confidence: z.string(),
  reason: z.string(),
  evidence: z.array(knowledgeEvidenceSchema),
});

export const knowledgeGraphSchema = z.object({
  available: z.boolean(),
  generated_at: z.string().nullable(),
  nodes: z.array(knowledgeNodeSchema),
  edges: z.array(knowledgeEdgeSchema),
  counts: knowledgeCountsSchema,
  next_cursor: z.string().nullable(),
  total_nodes: z.number(),
  total_edges: z.number(),
});

export const knowledgeSearchResultSchema = z
  .object({
    id: z.string(),
    type: z.string(),
    title: z.string(),
    resource: z.string(),
    snippet: z.string().optional(),
    rank: z.number().optional(),
    score: z.number().optional(),
  })
  .catchall(z.unknown());

export const knowledgeSearchSchema = z.object({
  available: z.boolean(),
  mode: z.enum(["fulltext", "semantic"]),
  query: z.string(),
  status: z.string(),
  message: z.string(),
  results: z.array(knowledgeSearchResultSchema),
});

export const contextConceptSchema = z
  .object({
    id: z.string(),
    type: z.string().nullable().optional(),
    title: z.string().nullable().optional(),
    description: z.string().nullable().optional(),
    resource: z.string().nullable().optional(),
    doc: z.string().nullable().optional(),
    tags: z.array(z.unknown()).optional(),
    body_preview: z.string().optional(),
    snippet: z.string().optional(),
    rank: z.number().optional(),
  })
  .catchall(z.unknown());

export const contextPackSchema = z
  .object({
    query: z.string(),
    budget: z.enum(["tiny", "focused", "full"]),
    matches: z.array(contextConceptSchema),
    expanded_concepts: z.array(contextConceptSchema),
    evidence_edges: z.array(z.record(z.string(), z.unknown())),
    estimated_tokens: z.number(),
    why: z.array(z.string()),
  })
  .catchall(z.unknown());

export const knowledgeContextSchema = z.object({
  available: z.boolean(),
  query: z.string(),
  budget: z.enum(["tiny", "focused", "full"]),
  status: z.string(),
  message: z.string(),
  pack: contextPackSchema.nullable(),
});

export const knowledgePreflightSchema = z.object({
  task: z.string(),
  report: z
    .object({
      task: z.string(),
      scope: z.string(),
      risk_flags: z.array(z.string()),
      likely_areas: z.array(z.string()),
      recommended_budget: z.enum(["tiny", "focused", "full"]),
      index_state: z.string(),
      why: z.array(z.string()),
    })
    .catchall(z.unknown()),
});

export const knowledgeUsageEntrySchema = z
  .object({
    timestamp: z.string(),
    client: z.string(),
    entrypoint: z.string(),
    action: z.string(),
    query_preview: z.string(),
    budget: z.string(),
    included_concepts: z.array(z.string()),
    evidence_edge_count: z.number(),
    estimated_tokens: z.number(),
    cache_state: z.string(),
    duration_ms: z.number(),
  })
  .catchall(z.unknown());

export const knowledgeUsageSchema = z.object({
  entries: z.array(knowledgeUsageEntrySchema),
  usage_path: z.string(),
  total_entries: z.number(),
});

export type KnowledgeSummary = z.infer<typeof knowledgeSummarySchema>;
export type KnowledgeNode = z.infer<typeof knowledgeNodeSchema>;
export type KnowledgeEdge = z.infer<typeof knowledgeEdgeSchema>;
export type KnowledgeGraph = z.infer<typeof knowledgeGraphSchema>;
export type KnowledgeSearchResult = z.infer<typeof knowledgeSearchResultSchema>;
export type KnowledgeSearch = z.infer<typeof knowledgeSearchSchema>;
export type ContextPack = z.infer<typeof contextPackSchema>;
export type KnowledgeContext = z.infer<typeof knowledgeContextSchema>;
export type KnowledgePreflight = z.infer<typeof knowledgePreflightSchema>;
export type KnowledgeUsage = z.infer<typeof knowledgeUsageSchema>;

export interface KnowledgeGraphFilters {
  query: string;
  type: string;
  relation: string;
}

export function useKnowledgeSummary() {
  return useQuery({
    queryKey: queryKeys.global("knowledge", "summary"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/knowledge", knowledgeSummarySchema, signal);
      return requireData(envelope, "knowledge summary");
    },
    staleTime: 20_000,
  });
}

export function useKnowledgeGraph(filters: KnowledgeGraphFilters) {
  return useQuery({
    queryKey: queryKeys.global(
      "knowledge",
      "graph",
      filters.query,
      filters.type || "all-types",
      filters.relation || "all-relations",
    ),
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ limit: "900" });
      if (filters.query.trim()) params.set("q", filters.query.trim());
      if (filters.type) params.set("type", filters.type);
      if (filters.relation) params.set("relation", filters.relation);
      const nodes = new Map<string, KnowledgeNode>();
      const edges = new Map<string, KnowledgeEdge>();
      let page: KnowledgeGraph | null = null;
      do {
        if (page?.next_cursor) params.set("cursor", page.next_cursor);
        const envelope = await apiGet(
          `/api/knowledge/graph?${params.toString()}`,
          knowledgeGraphSchema,
          signal,
        );
        page = requireData(envelope, "knowledge graph");
        for (const node of page.nodes) nodes.set(node.id, node);
        for (const edge of page.edges) edges.set(edge.id, edge);
      } while (page.next_cursor !== null);
      return {
        ...page,
        nodes: [...nodes.values()],
        edges: [...edges.values()],
        next_cursor: null,
      } satisfies KnowledgeGraph;
    },
    staleTime: 20_000,
  });
}

export function useKnowledgeSearch(query: string, mode: "fulltext" | "semantic") {
  return useQuery({
    queryKey: queryKeys.global("knowledge", "search", mode, query),
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ q: query, mode, limit: "12" });
      const envelope = await apiGet(
        `/api/knowledge/search?${params.toString()}`,
        knowledgeSearchSchema,
        signal,
      );
      return requireData(envelope, "knowledge search");
    },
    enabled: query.trim().length > 0,
    staleTime: 10_000,
  });
}

export function useKnowledgeContextPack(query: string, budget: "tiny" | "focused" | "full") {
  return useQuery({
    queryKey: queryKeys.global("knowledge", "context", budget, query),
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ q: query, budget });
      const envelope = await apiGet(
        `/api/knowledge/context-pack?${params.toString()}`,
        knowledgeContextSchema,
        signal,
      );
      return requireData(envelope, "knowledge context pack");
    },
    enabled: query.trim().length > 0,
    staleTime: 10_000,
  });
}

export function useKnowledgePreflight(task: string) {
  return useQuery({
    queryKey: queryKeys.global("knowledge", "preflight", task),
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ task });
      const envelope = await apiGet(
        `/api/knowledge/preflight?${params.toString()}`,
        knowledgePreflightSchema,
        signal,
      );
      return requireData(envelope, "knowledge preflight");
    },
    enabled: task.trim().length > 0,
    staleTime: 10_000,
  });
}

export function useKnowledgeUsage(limit = 20) {
  return useQuery({
    queryKey: queryKeys.global("knowledge", "usage", limit),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/knowledge/usage?limit=${limit}`,
        knowledgeUsageSchema,
        signal,
      );
      return requireData(envelope, "knowledge usage");
    },
    staleTime: 15_000,
  });
}
