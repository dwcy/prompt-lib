// Zod schemas + TanStack Query hooks for the Agent Setup module's Skills view: the installed
// skill inventory, one skill's parsed structure, and one of its bundled files.
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { useProjectContextStore } from "@/stores/projectContext";

export const skillScopeSchema = z.enum(["user", "project", "plugin"]);
export const skillKindSchema = z.enum(["skill", "command"]);
export const skillPrecedenceSchema = z.enum(["effective", "shadowed", "ambiguous", "not_loaded"]);
export const skillDriftSchema = z.enum(["in_sync", "differs", "not_in_repo", "not_applicable"]);

export const skillSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  invocation: z.string(),
  scope: skillScopeSchema,
  kind: skillKindSchema,
  plugin: z.string().nullable(),
  marketplace: z.string().nullable(),
  plugin_enabled: z.boolean().nullable(),
  description: z.string(),
  allowed_tools: z.array(z.string()),
  model: z.string().nullable(),
  argument_hint: z.string().nullable(),
  path: z.string(),
  dir_path: z.string().nullable(),
  size_bytes: z.number().nullable(),
  line_count: z.number(),
  heading_count: z.number(),
  modified_at: z.string().nullable(),
  bundled_count: z.number(),
  loaded: z.boolean(),
  not_loaded_reason: z.string().nullable(),
  precedence: skillPrecedenceSchema,
  duplicates: z.array(z.string()),
  drift: skillDriftSchema,
});

export const skillSourceSchema = z.object({
  key: z.string(),
  label: z.string(),
  scope: skillScopeSchema,
  path: z.string(),
  exists: z.boolean(),
  count: z.number(),
  plugin_version: z.string().nullable(),
  plugin_enabled: z.boolean().nullable(),
});

export const skillInventorySchema = z.object({
  project_path: z.string().nullable(),
  claude_home: z.string(),
  repo_skills_path: z.string().nullable(),
  counts: z.record(z.string(), z.number()),
  sources: z.array(skillSourceSchema),
  skills: z.array(skillSummarySchema),
  unapplied_repo_skills: z.array(z.object({ name: z.string(), path: z.string() })),
});

export const skillBlockSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("paragraph"), text: z.string() }),
  z.object({ type: z.literal("code"), language: z.string().nullable(), text: z.string() }),
  z.object({
    type: z.literal("list"),
    ordered: z.boolean(),
    items: z.array(z.object({ text: z.string(), depth: z.number() })),
  }),
  z.object({
    type: z.literal("table"),
    header: z.array(z.string()),
    rows: z.array(z.array(z.string())),
  }),
  z.object({ type: z.literal("quote"), text: z.string() }),
  z.object({ type: z.literal("divider") }),
]);

export const skillSectionSchema = z.object({
  level: z.number(),
  title: z.string(),
  anchor: z.string(),
  blocks: z.array(skillBlockSchema),
});

export const skillReferenceSchema = z.object({
  label: z.string(),
  target_id: z.string().nullish(),
  resolved: z.boolean(),
  path: z.string().nullish(),
});

export const skillBundledFileSchema = z.object({
  name: z.string(),
  rel_path: z.string(),
  group: z.string(),
  size_bytes: z.number().nullable(),
  previewable: z.boolean(),
});

export const skillDetailSchema = skillSummarySchema.extend({
  frontmatter_raw: z.string(),
  frontmatter: z.record(z.string(), z.unknown()),
  preamble: z.array(skillBlockSchema),
  sections: z.array(skillSectionSchema),
  raw: z.string(),
  truncated: z.boolean(),
  bundled_files: z.array(skillBundledFileSchema),
  references: z.object({
    skills: z.array(skillReferenceSchema),
    agents: z.array(skillReferenceSchema),
    tools: z.array(skillReferenceSchema),
    files: z.array(skillReferenceSchema),
  }),
  repo_source_path: z.string().nullable(),
});

export const skillAssetSchema = z.object({
  skill_id: z.string(),
  rel_path: z.string(),
  path: z.string(),
  content: z.string().nullable(),
  binary: z.boolean(),
  truncated: z.boolean(),
  size_bytes: z.number(),
});

export type SkillScope = z.infer<typeof skillScopeSchema>;
export type SkillKind = z.infer<typeof skillKindSchema>;
export type SkillPrecedence = z.infer<typeof skillPrecedenceSchema>;
export type SkillDrift = z.infer<typeof skillDriftSchema>;
export type SkillSummary = z.infer<typeof skillSummarySchema>;
export type SkillSource = z.infer<typeof skillSourceSchema>;
export type SkillInventory = z.infer<typeof skillInventorySchema>;
export type SkillBlock = z.infer<typeof skillBlockSchema>;
export type SkillSection = z.infer<typeof skillSectionSchema>;
export type SkillReference = z.infer<typeof skillReferenceSchema>;
export type SkillBundledFile = z.infer<typeof skillBundledFileSchema>;
export type SkillDetail = z.infer<typeof skillDetailSchema>;
export type SkillAsset = z.infer<typeof skillAssetSchema>;

// Plugin and project skills both depend on which project is selected, so every skill query is
// project-scoped — switching projects has to rebuild the inventory.
export function useSkillInventory() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped("agentConfig", projectPath, "skills"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/agent-config/skills", skillInventorySchema, signal);
      return requireData(envelope, "skill inventory");
    },
    staleTime: 15_000,
  });
}

export function useSkillDetail(skillId: string | null) {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped("agentConfig", projectPath, "skillDetail", skillId ?? "none"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/agent-config/skills/detail?skill_id=${encodeURIComponent(skillId ?? "")}`,
        skillDetailSchema,
        signal,
      );
      return requireData(envelope, "skill detail");
    },
    enabled: skillId !== null,
    staleTime: 15_000,
  });
}

export function useSkillAsset(skillId: string | null, relPath: string | null) {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped(
      "agentConfig",
      projectPath,
      "skillAsset",
      skillId ?? "none",
      relPath ?? "none",
    ),
    queryFn: async ({ signal }) => {
      const query = `skill_id=${encodeURIComponent(skillId ?? "")}&rel_path=${encodeURIComponent(relPath ?? "")}`;
      const envelope = await apiGet(
        `/api/agent-config/skills/asset?${query}`,
        skillAssetSchema,
        signal,
      );
      return requireData(envelope, "skill asset");
    },
    enabled: skillId !== null && relPath !== null,
    staleTime: 15_000,
  });
}
