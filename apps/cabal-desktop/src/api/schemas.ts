// Zod schemas for the backend's SnapshotEnvelope v2 wire format and shared entities.
import { z } from "zod";

export const SCHEMA_VERSION = "cabal-web.v2" as const;

export const envelopeStatusSchema = z.enum(["ok", "degraded", "error"]);
export const moduleStateSchema = z.enum(["ok", "loading", "degraded", "failed", "unavailable"]);
export const diagnosticSeveritySchema = z.enum(["info", "warning", "error"]);
export const diagnosticKindSchema = z.enum(["data_source", "mutation", "backend"]);
export const jobStateSchema = z.enum(["queued", "running", "succeeded", "failed", "cancelled"]);

export const envelopeErrorSchema = z
  .object({
    code: z.string(),
    message: z.string(),
  })
  .catchall(z.unknown());

export const moduleHealthSchema = z.object({
  module: z.string(),
  state: moduleStateSchema,
  detail: z.string(),
  last_success_at: z.string().nullable(),
});

export const driftFlagsSchema = z.object({
  claude: z.boolean(),
  codex: z.boolean(),
});

export const healthPayloadSchema = z.object({
  version: z.string(),
  started_at: z.string(),
  modules: z.array(moduleHealthSchema),
  drift_flags: driftFlagsSchema.optional(),
  project_branch: z.string().nullable().optional(),
});

export const diagnosticEventSchema = z.object({
  id: z.number(),
  severity: diagnosticSeveritySchema,
  module: z.string(),
  message: z.string(),
  occurred_at: z.string(),
  kind: diagnosticKindSchema,
});

export const jobRecordSchema = z.object({
  job_id: z.string(),
  kind: z.string(),
  ticket_id: z.string().nullable(),
  state: jobStateSchema,
  output_tail: z.array(z.string()),
  exit_detail: z.string().nullable(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});

export const effectPreviewSchema = z.object({
  summary: z.string(),
  commands: z.array(z.string()),
  files_changed: z.array(z.string()),
  scopes: z.array(z.string()),
  backup: z.string().nullable(),
  removals: z.array(z.string()),
});

export const confirmationTicketSchema = z.object({
  ticket_id: z.string(),
  action_id: z.string(),
  effect_preview: effectPreviewSchema,
  precondition_digest: z.string(),
  created_at: z.string(),
  expires_at: z.string(),
});

export const recentProjectSchema = z.object({
  path: z.string(),
  name: z.string(),
  action: z.string(),
  last_opened: z.string(),
});

export const projectContextSchema = z.object({
  path: z.string(),
  name: z.string(),
  is_git_repo: z.boolean(),
  recents: z.array(recentProjectSchema),
  selected_at: z.string().nullable(),
});

// The web-api contract test only pins OVERVIEW_SECTION_KEYS (presence) and drift_flags' two
// booleans — the internal shape of each aggregated section is not otherwise specified, so each
// section is modeled as an open record and read via lib/unknownFields.ts's narrowing helpers
// (same pattern as LogStream's extractLogLine narrowing an SSE frame's `data: unknown`).
export const overviewSectionSchema = z.record(z.string(), z.unknown());

export const overviewPayloadSchema = z.object({
  dashboard_summary: overviewSectionSchema,
  recent_sessions: z.array(overviewSectionSchema),
  account: overviewSectionSchema,
  doctor: overviewSectionSchema,
  knowledge_availability: overviewSectionSchema,
  security_summary: overviewSectionSchema,
  drift_flags: driftFlagsSchema,
});

// Per-section /api/dashboard?section= payload — same "shape not pinned by contract" caveat as
// overviewSectionSchema above; the `stale` flag itself already lives on the envelope.
export const dashboardSectionSchema = z.record(z.string(), z.unknown());

export const newsItemSchema = z.object({
  id: z.string(), source_id: z.string(), source_name: z.string(), category: z.string(),
  title: z.string(), canonical_url: z.string(), summary: z.string(),
  published_at: z.string().nullable(), tags: z.array(z.string()),
  read: z.boolean().optional(), saved: z.boolean().optional(),
  security: z.record(z.string(), z.unknown()).nullable(), service: z.record(z.string(), z.unknown()).nullable(),
});
export const newsSourceSchema = z.object({
  id: z.string(), name: z.string(), category: z.string(), endpoint: z.string(), format: z.string(),
  capabilities: z.array(z.string()), health: z.string(), error_hint: z.string().nullable(), enabled: z.boolean().optional(),
});
export const newsPayloadSchema = z.object({ items: z.array(newsItemSchema), sources: z.array(newsSourceSchema) });
export const newsItemStateSchema = z.object({ read: z.boolean(), saved: z.boolean() });
export const newsSourcesPayloadSchema = z.object({ sources: z.array(newsSourceSchema) });

export const diagnosticsListSchema = z.object({
  events: z.array(diagnosticEventSchema),
});

// Generic envelope factory: builds a Zod schema for SnapshotEnvelope<T> given T's data schema.
export function envelopeSchema<T extends z.ZodTypeAny>(dataSchema: T) {
  return z.object({
    schema_version: z.string(),
    captured_at: z.string(),
    status: envelopeStatusSchema,
    source: z.string(),
    stale: z.boolean(),
    precondition_digest: z.string().nullable(),
    data: dataSchema.nullable(),
    error: envelopeErrorSchema.nullable(),
  });
}

export type EnvelopeStatus = z.infer<typeof envelopeStatusSchema>;
export type ModuleState = z.infer<typeof moduleStateSchema>;
export type ModuleHealth = z.infer<typeof moduleHealthSchema>;
export type HealthPayload = z.infer<typeof healthPayloadSchema>;
export type DiagnosticEvent = z.infer<typeof diagnosticEventSchema>;
export type JobState = z.infer<typeof jobStateSchema>;
export type JobRecord = z.infer<typeof jobRecordSchema>;
export type EffectPreview = z.infer<typeof effectPreviewSchema>;
export type ConfirmationTicket = z.infer<typeof confirmationTicketSchema>;
export type EnvelopeError = z.infer<typeof envelopeErrorSchema>;
export type RecentProject = z.infer<typeof recentProjectSchema>;
export type ProjectContext = z.infer<typeof projectContextSchema>;
export type DriftFlags = z.infer<typeof driftFlagsSchema>;
export type OverviewSection = z.infer<typeof overviewSectionSchema>;
export type OverviewPayload = z.infer<typeof overviewPayloadSchema>;
export type DashboardSection = z.infer<typeof dashboardSectionSchema>;
export type NewsItem = z.infer<typeof newsItemSchema>;
export type NewsSource = z.infer<typeof newsSourceSchema>;
export type NewsPayload = z.infer<typeof newsPayloadSchema>;
export type DiagnosticsList = z.infer<typeof diagnosticsListSchema>;

export interface SnapshotEnvelope<T> {
  schema_version: string;
  captured_at: string;
  status: EnvelopeStatus;
  source: string;
  stale: boolean;
  precondition_digest: string | null;
  data: T | null;
  error: EnvelopeError | null;
}
