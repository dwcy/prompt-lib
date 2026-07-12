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

export const healthPayloadSchema = z.object({
  version: z.string(),
  started_at: z.string(),
  modules: z.array(moduleHealthSchema),
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
