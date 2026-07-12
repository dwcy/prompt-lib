// Envelope-v2 fixture builders matching the Zod schemas in src/api/schemas.ts exactly.
import {
  type ConfirmationTicket,
  type DiagnosticEvent,
  type DriftFlags,
  type EffectPreview,
  type EnvelopeError,
  type HealthPayload,
  type JobRecord,
  type JobState,
  type ModuleHealth,
  type OverviewPayload,
  type ProjectContext,
  type RecentProject,
  SCHEMA_VERSION,
  type SnapshotEnvelope,
} from "@/api/schemas";

const DEFAULT_TIMESTAMP = "2026-01-01T00:00:00Z";

const TERMINAL_JOB_STATES: ReadonlySet<JobState> = new Set(["succeeded", "failed", "cancelled"]);

export function buildModuleHealth(overrides: Partial<ModuleHealth> = {}): ModuleHealth {
  return {
    module: "config",
    state: "ok",
    detail: "nominal",
    last_success_at: DEFAULT_TIMESTAMP,
    ...overrides,
  };
}

export function buildHealthPayload(
  moduleCount = 0,
  overrides: Partial<HealthPayload> = {},
): HealthPayload {
  const modules = Array.from({ length: moduleCount }, (_, index) =>
    buildModuleHealth({ module: `module-${index}` }),
  );
  return {
    version: "0.0.0-test",
    started_at: DEFAULT_TIMESTAMP,
    modules,
    ...overrides,
  };
}

export function buildEffectPreview(overrides: Partial<EffectPreview> = {}): EffectPreview {
  return {
    summary: "Deploy 3 changed files to ~/.claude",
    commands: [],
    files_changed: ["agents/foo.md", "settings.json"],
    scopes: ["claude"],
    backup: "settings-backup",
    removals: [],
    ...overrides,
  };
}

export function buildConfirmationTicket(
  overrides: Partial<ConfirmationTicket> = {},
): ConfirmationTicket {
  return {
    ticket_id: "ticket-1",
    action_id: "config.apply",
    effect_preview: buildEffectPreview(),
    precondition_digest: "sha256:initial",
    created_at: DEFAULT_TIMESTAMP,
    expires_at: "2026-01-01T00:05:00Z",
    ...overrides,
  };
}

export function buildJobRecord(state: JobState, overrides: Partial<JobRecord> = {}): JobRecord {
  const terminal = TERMINAL_JOB_STATES.has(state);
  return {
    job_id: "job-1",
    kind: "config.apply",
    ticket_id: "ticket-1",
    state,
    output_tail: [],
    exit_detail: terminal ? "exit 0" : null,
    created_at: DEFAULT_TIMESTAMP,
    started_at: state === "queued" ? null : DEFAULT_TIMESTAMP,
    finished_at: terminal ? "2026-01-01T00:01:00Z" : null,
    ...overrides,
  };
}

export function wrapEnvelope<T>(
  data: T,
  overrides: Partial<Omit<SnapshotEnvelope<T>, "data">> = {},
): SnapshotEnvelope<T> {
  return {
    schema_version: SCHEMA_VERSION,
    captured_at: DEFAULT_TIMESTAMP,
    status: "ok",
    source: "system",
    stale: false,
    precondition_digest: null,
    data,
    error: null,
    ...overrides,
  };
}

export function buildErrorEnvelope(
  error: EnvelopeError,
  overrides: Partial<Omit<SnapshotEnvelope<null>, "data" | "error">> = {},
): SnapshotEnvelope<null> {
  return {
    schema_version: SCHEMA_VERSION,
    captured_at: DEFAULT_TIMESTAMP,
    status: "error",
    source: "system",
    stale: false,
    precondition_digest: null,
    data: null,
    error,
    ...overrides,
  };
}

export function buildRecentProject(overrides: Partial<RecentProject> = {}): RecentProject {
  return {
    path: "/repos/example",
    name: "example",
    action: "open",
    last_opened: DEFAULT_TIMESTAMP,
    ...overrides,
  };
}

// selected_at non-null by default so <App/> renders the normal shell (not the project gate) in
// tests that don't care about the gate flow — see useProjectContextSync's doc comment.
export function buildProjectContext(overrides: Partial<ProjectContext> = {}): ProjectContext {
  return {
    path: "/repos/example",
    name: "example",
    is_git_repo: true,
    recents: [buildRecentProject()],
    selected_at: DEFAULT_TIMESTAMP,
    ...overrides,
  };
}

export function buildDriftFlags(overrides: Partial<DriftFlags> = {}): DriftFlags {
  return { claude: false, codex: false, ...overrides };
}

export function buildOverviewPayload(overrides: Partial<OverviewPayload> = {}): OverviewPayload {
  return {
    dashboard_summary: {},
    recent_sessions: [],
    account: {},
    doctor: {},
    knowledge_availability: {},
    security_summary: {},
    drift_flags: buildDriftFlags(),
    ...overrides,
  };
}

export function buildDiagnosticEvent(overrides: Partial<DiagnosticEvent> = {}): DiagnosticEvent {
  return {
    id: 1,
    severity: "info",
    module: "config",
    message: "nominal",
    occurred_at: DEFAULT_TIMESTAMP,
    kind: "data_source",
    ...overrides,
  };
}

export interface SseFrameInput {
  event: string;
  data: unknown;
  id?: number;
}

// Raw wire-format SSE frame text (event/id/data + blank-line terminator) matching sseFrames.ts's parser.
export function formatSseFrame({ event, data, id }: SseFrameInput): string {
  const idLine = id !== undefined ? `id: ${id}\n` : "";
  return `event: ${event}\n${idLine}data: ${JSON.stringify(data)}\n\n`;
}

// Builds a ReadableStream MSW can hand back as a streamed response body for a job/log/diagnostics
// SSE endpoint. `keepOpen` leaves the stream pending (never closes) to model an in-progress job
// without triggering the client's immediate-reconnect-on-clean-close behaviour.
export function buildSseStream(
  frames: SseFrameInput[],
  options: { keepOpen?: boolean } = {},
): ReadableStream<Uint8Array> {
  const { keepOpen = false } = options;
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(formatSseFrame(frame)));
      }
      if (!keepOpen) controller.close();
    },
  });
}
