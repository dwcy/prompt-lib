// Zod schemas + TanStack Query hooks for US3 config deployment, cleanup/restore, settings,
// local project config, and Codex parity endpoints.
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { useProjectContextStore } from "@/stores/projectContext";

export const configTargetSchema = z.enum(["claude", "codex"]);
export const configFileStateSchema = z.enum(["new", "changed", "unchanged"]);
export const previewStateSchema = z.enum(["new", "changed", "skip"]);
export const backupKindSchema = z.enum(["cleanup", "settings"]);
export const settingSourceSchema = z.enum(["global", "local_override", "unset"]);
export const conversionStateSchema = z.enum([
  "converted",
  "not-converted",
  "codex-only",
  "stale",
  "unsupported",
]);

export const configFileSchema = z.object({
  rel_path: z.string(),
  state: configFileStateSchema,
  diff_available: z.boolean(),
});

export const configComponentSchema = z.object({
  key: z.string(),
  label: z.string(),
  group: z.string(),
  files: z.array(configFileSchema),
});

export const driftReportSchema = z.object({
  target: configTargetSchema,
  changed_count: z.number(),
  new_count: z.number(),
  unchanged_count: z.number(),
  extras_count: z.number(),
  computed_at: z.string(),
  digest: z.string(),
});

export const configTreeSchema = z.object({
  target: configTargetSchema,
  components: z.array(configComponentSchema),
  drift: driftReportSchema,
});

export const configDiffSchema = z.object({
  target: configTargetSchema,
  rel_path: z.string(),
  state: configFileStateSchema,
  diff_text: z.string(),
});

export const configExtraSchema = z.object({
  rel_path: z.string(),
  classification: z.enum(["stale", "unknown"]),
  reason: z.string(),
});

export const configExtraGroupSchema = z.object({
  component: z.string(),
  label: z.string(),
  extras: z.array(configExtraSchema),
});

export const configExtrasSchema = z.object({
  target: configTargetSchema,
  groups: z.array(configExtraGroupSchema),
});

export const backupSetSchema = z.object({
  id: z.string(),
  kind: backupKindSchema,
  created_at: z.string(),
  files_count: z.number(),
  restorable: z.boolean(),
});

export const backupListSchema = z.object({
  kind: backupKindSchema,
  backups: z.array(backupSetSchema),
});

export const settingEntrySchema = z.object({
  key: z.string(),
  label: z.string(),
  description: z.string(),
  source: settingSourceSchema,
  value_state: z.boolean(),
  target_file: z.string(),
});

export const settingsPayloadSchema = z.object({
  entries: z.array(settingEntrySchema),
  project_selected: z.boolean(),
});

export const previewItemSchema = z.object({
  key: z.string(),
  rel_path: z.string(),
  state: previewStateSchema,
  selected: z.boolean(),
});

export const localConfigActionSchema = z.object({
  key: z.string(),
  label: z.string(),
  applicable: z.boolean(),
  applied_state: z.string(),
  preview_items: z.array(previewItemSchema),
});

export const optionSchema = z.object({
  value: z.string(),
  label: z.string(),
});

export const localConfigPayloadSchema = z.object({
  actions: z.array(localConfigActionSchema),
  template_options: z.array(optionSchema),
  gitignore_options: z.array(z.string()).optional(),
  project_selected: z.boolean(),
});

export const conversionRowSchema = z.object({
  asset: z.string(),
  state: conversionStateSchema,
  kind: z.string(),
  source_path: z.string().nullable(),
  output_path: z.string().nullable(),
  reason: z.string(),
});

export const conversionPayloadSchema = z.object({
  rows: z.array(conversionRowSchema),
});

export type ConfigTarget = z.infer<typeof configTargetSchema>;
export type ConfigFileState = z.infer<typeof configFileStateSchema>;
export type ConfigFile = z.infer<typeof configFileSchema>;
export type ConfigComponent = z.infer<typeof configComponentSchema>;
export type ConfigTree = z.infer<typeof configTreeSchema>;
export type ConfigDiff = z.infer<typeof configDiffSchema>;
export type ConfigExtraGroup = z.infer<typeof configExtraGroupSchema>;
export type BackupKind = z.infer<typeof backupKindSchema>;
export type BackupSet = z.infer<typeof backupSetSchema>;
export type SettingEntry = z.infer<typeof settingEntrySchema>;
export type LocalConfigAction = z.infer<typeof localConfigActionSchema>;
export type LocalConfigPayload = z.infer<typeof localConfigPayloadSchema>;
export type ConversionRow = z.infer<typeof conversionRowSchema>;

export function useConfigTree(target: ConfigTarget) {
  return useQuery({
    queryKey: queryKeys.global("config", "tree", target),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(`/api/config/tree?target=${target}`, configTreeSchema, signal);
      return requireData(envelope, `${target} config tree`);
    },
    staleTime: 15_000,
  });
}

export function useConfigDiff(target: ConfigTarget, path: string | null) {
  return useQuery({
    queryKey: queryKeys.global("config", "diff", target, path ?? "none"),
    queryFn: async ({ signal }) => {
      const queryPath = encodeURIComponent(path ?? "");
      const envelope = await apiGet(
        `/api/config/diff?target=${target}&path=${queryPath}`,
        configDiffSchema,
        signal,
      );
      return requireData(envelope, `${target} config diff`);
    },
    enabled: path !== null,
    staleTime: 15_000,
  });
}

export function useConfigExtras(target: ConfigTarget) {
  return useQuery({
    queryKey: queryKeys.global("config", "extras", target),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/config/extras?target=${target}`,
        configExtrasSchema,
        signal,
      );
      return requireData(envelope, `${target} extras`);
    },
    staleTime: 15_000,
  });
}

export function useConfigBackups(kind: BackupKind) {
  return useQuery({
    queryKey: queryKeys.global("config", "backups", kind),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(`/api/config/backups?kind=${kind}`, backupListSchema, signal);
      return requireData(envelope, `${kind} backups`);
    },
    staleTime: 15_000,
  });
}

export function useSettings() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped("settings", projectPath),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/settings", settingsPayloadSchema, signal);
      return requireData(envelope, "settings");
    },
    staleTime: 15_000,
  });
}

export function useLocalConfig(template: string | null, gitignore: string | null) {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped(
      "localConfig",
      projectPath,
      template ?? "default-template",
      gitignore ?? "default-gitignore",
    ),
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams();
      if (template !== null) params.set("template", template);
      if (gitignore !== null) params.set("gitignore", gitignore);
      const suffix = params.size > 0 ? `?${params.toString()}` : "";
      const envelope = await apiGet(`/api/local-config${suffix}`, localConfigPayloadSchema, signal);
      return requireData(envelope, "local config");
    },
    staleTime: 10_000,
  });
}

export function useCodexConversion() {
  return useQuery({
    queryKey: queryKeys.global("codex", "conversion"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/codex/conversion", conversionPayloadSchema, signal);
      return requireData(envelope, "codex conversion");
    },
    staleTime: 30_000,
  });
}

export function useCodexLocalConfig(template: string | null) {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped("localConfig", projectPath, "codex", template ?? "default-template"),
    queryFn: async ({ signal }) => {
      const suffix = template !== null ? `?template=${encodeURIComponent(template)}` : "";
      const envelope = await apiGet(
        `/api/codex/local-config${suffix}`,
        localConfigPayloadSchema,
        signal,
      );
      return requireData(envelope, "codex local config");
    },
    staleTime: 10_000,
  });
}
