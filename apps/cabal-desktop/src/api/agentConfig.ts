// Zod schemas + TanStack Query hooks for the Agent Setup module's read-only folder/file
// browser over Claude/Codex/Antigravity global and per-project local config directories.
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { useProjectContextStore } from "@/stores/projectContext";

export const agentKeySchema = z.enum(["claude", "codex", "antigravity"]);
export const agentConfigScopeSchema = z.enum(["global", "local"]);
export const agentConfigEntryKindSchema = z.enum(["dir", "file"]);

export interface AgentConfigEntry {
  name: string;
  rel_path: string;
  kind: z.infer<typeof agentConfigEntryKindSchema>;
  size_bytes: number | null;
  modified_at: string | null;
  children: AgentConfigEntry[] | null;
}

export const agentConfigEntrySchema: z.ZodType<AgentConfigEntry> = z.lazy(() =>
  z.object({
    name: z.string(),
    rel_path: z.string(),
    kind: agentConfigEntryKindSchema,
    size_bytes: z.number().nullable(),
    modified_at: z.string().nullable(),
    children: z.array(agentConfigEntrySchema).nullable(),
  }),
);

export const agentConfigTreeSchema = z.object({
  agent: agentKeySchema,
  scope: agentConfigScopeSchema,
  base_path: z.string(),
  exists: z.boolean(),
  roots: z.array(agentConfigEntrySchema),
  truncated: z.boolean(),
});

export const agentConfigFileSchema = z.object({
  rel_path: z.string(),
  content: z.string().nullable(),
  binary: z.boolean(),
  truncated: z.boolean(),
  size_bytes: z.number(),
});

export type AgentKey = z.infer<typeof agentKeySchema>;
export type AgentConfigScope = z.infer<typeof agentConfigScopeSchema>;
export type AgentConfigTree = z.infer<typeof agentConfigTreeSchema>;
export type AgentConfigFile = z.infer<typeof agentConfigFileSchema>;

export function useAgentConfigTree(agent: AgentKey, scope: AgentConfigScope) {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey:
      scope === "global"
        ? queryKeys.global("agentConfig", "tree", agent, scope)
        : queryKeys.scoped("agentConfig", projectPath, "tree", agent, scope),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/agent-config/tree?agent=${agent}&scope=${scope}`,
        agentConfigTreeSchema,
        signal,
      );
      return requireData(envelope, `${agent} ${scope} config tree`);
    },
    staleTime: 15_000,
  });
}

export function useAgentConfigFile(
  agent: AgentKey,
  scope: AgentConfigScope,
  relPath: string | null,
) {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey:
      scope === "global"
        ? queryKeys.global("agentConfig", "file", agent, scope, relPath ?? "none")
        : queryKeys.scoped("agentConfig", projectPath, "file", agent, scope, relPath ?? "none"),
    queryFn: async ({ signal }) => {
      const queryPath = encodeURIComponent(relPath ?? "");
      const envelope = await apiGet(
        `/api/agent-config/file?agent=${agent}&scope=${scope}&rel_path=${queryPath}`,
        agentConfigFileSchema,
        signal,
      );
      return requireData(envelope, `${agent} ${scope} config file`);
    },
    enabled: relPath !== null,
    staleTime: 15_000,
  });
}
