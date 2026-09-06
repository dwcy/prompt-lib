// Envelope-v2 fixture builders matching the Zod schemas in src/api/schemas.ts exactly.

import type {
  EnvSourcesPayload,
  RevealResult,
  VariableContainer,
  VariableEntry,
  VariableSource,
} from "@/api/envSources";
import type { ProviderState } from "@/api/projectLifecycle";
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
import type { SystemOverview } from "@/api/systemOverview";
import type {
  ToolCatalogItem,
  ToolCatalogPayload,
  ToolDetail,
  ToolStatusEntry,
  ToolStatusState,
} from "@/api/tools";

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

export function buildProviderState(overrides: Partial<ProviderState> = {}): ProviderState {
  return {
    authenticated: true,
    accounts: [
      {
        user: "octocat",
        host: "github.com",
        active: true,
        valid: true,
        storage: "keyring",
      },
    ],
    active_account: "octocat",
    gh_status: "authenticated",
    login: { state: "idle" },
    ...overrides,
  };
}

export function buildSystemOverview(overrides: Partial<SystemOverview> = {}): SystemOverview {
  return {
    cabal: {
      version: "0.1.0",
      status: "up_to_date",
      local_hash: "abc12345",
      latest_hash: "abc12345",
      latest_date: "2026-08-11",
      behind_count: null,
      branch: "main",
      subject: "",
    },
    machine: {
      os: "Windows",
      release: "11",
      package_manager: "winget",
      tools: [
        { key: "git", label: "Git", installed: true, version: "git version 2.51.0" },
        { key: "python", label: "Python", installed: true, version: "3.14.0" },
        { key: "node", label: "Node.js", installed: true, version: "v24.0.0" },
        { key: "npm", label: "npm", installed: true, version: "11.0.0" },
        { key: "pnpm", label: "pnpm", installed: true, version: "10.0.0" },
        { key: "dotnet", label: ".NET SDK", installed: true, version: "10.0.100" },
        { key: "gh", label: "GitHub CLI", installed: true, version: null },
      ],
    },
    terminal: {
      default_terminal: "Windows Terminal",
      default_profile: "PowerShell",
      shells: [
        {
          key: "pwsh",
          label: "PowerShell",
          installed: true,
          version: "PowerShell 7.6.3",
          path: "C:\\Program Files\\PowerShell\\7\\pwsh.exe",
          active: true,
          configured: true,
          profile_path: "C:\\Users\\test\\Documents\\PowerShell\\profile.ps1",
        },
        {
          key: "cmd",
          label: "Command Prompt",
          installed: true,
          version: "Microsoft Windows [Version 11.0.1]",
          path: "C:\\Windows\\system32\\cmd.exe",
          active: false,
          configured: false,
          profile_path: null,
        },
      ],
      applications: [
        {
          key: "windows-terminal",
          label: "Windows Terminal",
          installed: true,
          version: null,
          path: "C:\\Windows\\wt.exe",
          configured: true,
          settings_path: "C:\\Users\\test\\AppData\\Local\\Terminal\\settings.json",
          active: true,
        },
      ],
      modifications: [
        {
          key: "tool:oh-my-posh",
          label: "Oh My Posh",
          detail: "Loaded by a shell profile",
          kind: "prompt",
          source: "C:\\Users\\test\\Documents\\PowerShell\\profile.ps1",
        },
        {
          key: "fonts",
          label: "Fonts",
          detail: "CaskaydiaCove Nerd Font",
          kind: "appearance",
          source: "C:\\Users\\test\\AppData\\Local\\Terminal\\settings.json",
        },
      ],
    },
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

export function buildToolCatalogItem(overrides: Partial<ToolCatalogItem> = {}): ToolCatalogItem {
  return {
    key: "git",
    label: "Git",
    category: "System & VCS",
    description: "Distributed version control used by nearly every project workflow.",
    source_url: "https://git-scm.com/",
    source_state: "verified",
    install_channel: "package",
    platforms: ["all"],
    badges: [],
    safety_notes: [],
    backup_policy: null,
    versions_available: ["2.44.0", "2.45.0"],
    ...overrides,
  };
}

export function buildToolStatusEntry(
  key: string,
  state: ToolStatusState,
  overrides: Partial<ToolStatusEntry> = {},
): ToolStatusEntry {
  return {
    key,
    state,
    current_version: state === "missing" ? null : "2.44.0",
    latest_version: "2.45.0",
    checked_at: DEFAULT_TIMESTAMP,
    ...overrides,
  };
}

export function buildToolCatalogPayload(
  items: ToolCatalogItem[],
  overrides: Partial<ToolCatalogPayload> = {},
): ToolCatalogPayload {
  const categoryCounts: Record<string, number> = {};
  const channelCounts: Record<string, number> = {};
  for (const item of items) {
    categoryCounts[item.category] = (categoryCounts[item.category] ?? 0) + 1;
    channelCounts[item.install_channel] = (channelCounts[item.install_channel] ?? 0) + 1;
  }
  return { items, category_counts: categoryCounts, channel_counts: channelCounts, ...overrides };
}

export function buildToolDetail(overrides: Partial<ToolDetail> = {}): ToolDetail {
  const { status, ...itemOverrides } = overrides;
  const item = buildToolCatalogItem(itemOverrides);
  return {
    ...item,
    status: status ?? {
      state: "missing",
      current_version: null,
      latest_version: item.versions_available.at(-1) ?? null,
      checked_at: DEFAULT_TIMESTAMP,
    },
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

// -- environment variable sources (020-env-variable-sources) --------------
// One builder per source state, so a test can assemble the exact degradation matrix row it
// is asserting on without restating the whole payload shape.

export function buildVariableEntry(overrides: Partial<VariableEntry> = {}): VariableEntry {
  return {
    name: "DATABASE_URL",
    source_id: "repo_file:.env.local",
    container_id: "repo_file:.env.local",
    description: "",
    target: null,
    entry_type: null,
    updated_at: null,
    retrievability: "readable",
    retrievability_reason: null,
    is_reference: false,
    ...overrides,
  };
}

export function buildVariableContainer(
  overrides: Partial<VariableContainer> = {},
): VariableContainer {
  return {
    id: "repo_file:.env.local",
    source_id: "repo_file:.env.local",
    label: ".env.local",
    qualifier: null,
    layer: null,
    entries: [buildVariableEntry()],
    ...overrides,
  };
}

export function buildVariableSource(overrides: Partial<VariableSource> = {}): VariableSource {
  return {
    id: "repo_file:.env.local",
    kind: "repo_file",
    label: ".env.local",
    state: "ok",
    hint: null,
    outside_repository: false,
    link_confidence: null,
    link_reason: null,
    containers: [buildVariableContainer()],
    ...overrides,
  };
}

/** A source that is reachable and authenticated but holds nothing (FR-037 `empty`). */
export function buildEmptySource(overrides: Partial<VariableSource> = {}): VariableSource {
  return buildVariableSource({
    id: "github",
    kind: "github",
    label: "GitHub",
    state: "empty",
    outside_repository: true,
    containers: [],
    ...overrides,
  });
}

/** A source detected but not fully readable; `hint` always states why (FR-034/35/36). */
export function buildDegradedSource(overrides: Partial<VariableSource> = {}): VariableSource {
  return buildVariableSource({
    id: "azure_keyvault",
    kind: "azure_keyvault",
    label: "Key Vault",
    state: "degraded",
    hint: "Azure sign-in is required — run `az login`",
    outside_repository: true,
    link_confidence: "machine_default",
    link_reason: "this machine's default Azure sign-in — not a link to this project",
    containers: [],
    ...overrides,
  });
}

export function buildEnvSourcesPayload(
  sources: VariableSource[] = [buildVariableSource()],
  overrides: Partial<EnvSourcesPayload> = {},
): EnvSourcesPayload {
  return {
    sources,
    project: "C:/projects/example",
    scanned_at: "2026-08-29T09:20:00Z",
    notices: [],
    ...overrides,
  };
}

export function buildRevealResult(overrides: Partial<RevealResult> = {}): RevealResult {
  return {
    status: "revealed",
    value: "postgres://localhost/app",
    reason: null,
    is_reference: false,
    ...overrides,
  };
}
