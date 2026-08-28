import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useJob } from "@/api/jobs";
import {
  type InitStagedFile,
  type InitTemplate,
  useInitPlan,
  useInitTemplates,
} from "@/api/projectLifecycle";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import "./InitProjectModule.css";

const DEFAULT_PARENT = "C:\\projects";
const DEFAULT_MCP_JSON = '{\n  "mcpServers": {}\n}';

export function InitProjectModule() {
  const queryClient = useQueryClient();
  const templatesQuery = useInitTemplates();
  const [parent, setParent] = useState(DEFAULT_PARENT);
  const [name, setName] = useState("new-project");
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [runClaude, setRunClaude] = useState(true);
  const [stageMcp, setStageMcp] = useState(false);
  const [mcpJson, setMcpJson] = useState(DEFAULT_MCP_JSON);
  const [browseError, setBrowseError] = useState<string | null>(null);
  const initializedPlanRef = useRef<string | null>(null);
  const initAction = useAction("init.apply");
  const planQuery = useInitPlan({
    dest: parent,
    name,
    template: templateId,
    enabled: parent.trim().length > 0 && name.trim().length > 0,
  });
  const jobQuery = useJob(initAction.jobId ?? "", {
    enabled: initAction.jobId !== null,
    refetchInterval: 1_000,
  });

  const templates = useMemo(
    () => [...(templatesQuery.data?.local ?? []), ...(templatesQuery.data?.github ?? [])],
    [templatesQuery.data],
  );

  useEffect(() => {
    if (templateId !== null || templatesQuery.data?.default_template == null) return;
    setTemplateId(templatesQuery.data.default_template);
  }, [templateId, templatesQuery.data]);

  useEffect(() => {
    if (planQuery.data === undefined) return;
    const planKey = `${planQuery.data.destination}\u0000${templateId ?? ""}\u0000${planQuery.data.staged_files
      .map((file) => `${file.rel_path}:${file.selected ? "1" : "0"}`)
      .join("\u0000")}`;
    if (initializedPlanRef.current === planKey) return;
    initializedPlanRef.current = planKey;
    setSelectedFiles(
      new Set(
        planQuery.data.staged_files.filter((file) => file.selected).map((file) => file.rel_path),
      ),
    );
  }, [planQuery.data, templateId]);

  useEffect(() => {
    if (jobQuery.data?.state !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.project.current() });
  }, [jobQuery.data, queryClient]);

  const selectedTemplate = templates.find((template) => template.id === templateId) ?? null;
  const stagedFiles = planQuery.data?.staged_files ?? [];
  const fileGroups = groupStagedFiles(stagedFiles);
  const selectedCount = selectedFiles.size;
  const totalBytes = stagedFiles
    .filter((file) => selectedFiles.has(file.rel_path))
    .reduce((sum, file) => sum + file.size_bytes, 0);
  const mcpJsonError = stageMcp ? validateMcpJson(mcpJson) : null;

  async function browseParent(): Promise<void> {
    setBrowseError(null);
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, multiple: false });
      if (typeof selected === "string") setParent(selected);
    } catch {
      setBrowseError("Native folder picker unavailable. The parent path remains editable.");
    }
  }

  function toggleFile(file: InitStagedFile): void {
    setSelectedFiles((current) => {
      const next = new Set(current);
      if (next.has(file.rel_path)) next.delete(file.rel_path);
      else next.add(file.rel_path);
      return next;
    });
  }

  function prepareApply(): void {
    if (templateId === null || mcpJsonError !== null) return;
    initAction.prepare({
      dest: parent.trim(),
      name: name.trim(),
      template: templateId,
      selected_files: [...selectedFiles],
      run_claude: runClaude,
      mcp_json: stageMcp ? mcpJson : "",
    });
  }

  return (
    <div className="init-workbench">
      <section className="init-build-runway">
        <div>
          <span className="init-eyebrow select-none">Project assembly</span>
          <strong>{planQuery.data?.destination ?? `${parent}\\${name}`}</strong>
        </div>
        <ol className="init-build-runway__steps" aria-label="Project creation workflow">
          <li className={planQuery.data?.name_valid ? "is-ready" : ""}>
            <span>01</span>
            <strong>Target</strong>
          </li>
          <li className={selectedTemplate === null ? "" : "is-ready"}>
            <span>02</span>
            <strong>Template</strong>
          </li>
          <li className={selectedCount === 0 ? "" : "is-ready"}>
            <span>03</span>
            <strong>{selectedCount} files</strong>
          </li>
          <li className="is-ready">
            <span>04</span>
            <strong>Handoff</strong>
          </li>
        </ol>
      </section>

      <section className="init-destination-panel">
        <div className="init-panel-heading">
          <span className="init-eyebrow select-none">Destination</span>
          <h2>Project target</h2>
        </div>
        <label className="init-field">
          <span>Parent folder</span>
          <div className="init-path-row">
            <input
              type="text"
              value={parent}
              onChange={(event) => setParent(event.target.value)}
              placeholder="C:\\projects"
              autoComplete="off"
              spellCheck={false}
            />
            <button type="button" onClick={() => void browseParent()}>
              Browse
            </button>
          </div>
        </label>
        {browseError !== null ? <p className="init-error">{browseError}</p> : null}
        <label className="init-field">
          <span>Project name</span>
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="my-new-project"
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        <div className="init-target-card">
          <StatePill
            variant={planQuery.data?.name_valid ? "ok" : "failed"}
            label={planQuery.data?.name_valid ? "ready" : "blocked"}
          />
          <span>{planQuery.data?.validation_message ?? "Enter a target and template."}</span>
          {planQuery.data !== undefined ? <code>{planQuery.data.destination}</code> : null}
        </div>
      </section>

      <section className="init-template-panel">
        <div className="init-panel-heading">
          <span className="init-eyebrow select-none">Template staging</span>
          <h2>{selectedTemplate?.label ?? "Choose a template"}</h2>
        </div>
        {templatesQuery.isPending ? (
          <EmptyState title="Loading templates..." />
        ) : templatesQuery.isError ? (
          <EmptyState title="Template catalog failed" body={templatesQuery.error.message} />
        ) : templates.length === 0 ? (
          <EmptyState title="No project templates available" />
        ) : (
          <div className="init-template-grid">
            {templates.map((template) => (
              <TemplateButton
                key={template.id}
                template={template}
                selected={template.id === templateId}
                onSelect={() => setTemplateId(template.id)}
              />
            ))}
          </div>
        )}
        <div className="init-stage-summary">
          <span>{selectedCount} staged</span>
          <span>{formatBytes(totalBytes)}</span>
          <span>{planQuery.data?.mcp_config.entries ?? 0} existing MCP entries</span>
        </div>
        {planQuery.isPending ? (
          <EmptyState title="Preparing staged preview..." />
        ) : planQuery.isError ? (
          <EmptyState title="Plan preview failed" body={planQuery.error.message} />
        ) : stagedFiles.length === 0 ? (
          <EmptyState title="No staged files yet" />
        ) : (
          <div className="init-file-stage">
            {fileGroups.map(([origin, files]) => (
              <section key={origin} className="init-file-group">
                <header>
                  <strong>{origin}</strong>
                  <span>
                    {files.filter((file) => selectedFiles.has(file.rel_path)).length}/{files.length}
                  </span>
                </header>
                {files.map((file) => (
                  <label
                    key={file.rel_path}
                    className={`init-file-row${selectedFiles.has(file.rel_path) ? " init-file-row--on" : ""}`}
                  >
                    <input
                      className="init-file-row__check"
                      type="checkbox"
                      checked={selectedFiles.has(file.rel_path)}
                      onChange={() => toggleFile(file)}
                    />
                    <span className="init-file-row__path">{file.rel_path}</span>
                    <span className="init-file-row__meta">
                      {file.state} / {formatBytes(file.size_bytes)}
                    </span>
                  </label>
                ))}
              </section>
            ))}
          </div>
        )}
      </section>

      <section className="init-handoff-panel">
        <div className="init-panel-heading">
          <span className="init-eyebrow select-none">Handoff</span>
          <h2>Apply and switch</h2>
        </div>
        <label className="init-toggle-row">
          <input
            type="checkbox"
            checked={runClaude}
            onChange={(event) => setRunClaude(event.target.checked)}
          />
          <span>Run Claude handoff after staging</span>
        </label>
        <label className="init-toggle-row">
          <input
            type="checkbox"
            checked={stageMcp}
            onChange={(event) => setStageMcp(event.target.checked)}
          />
          <span>Stage project MCP configuration</span>
        </label>
        {stageMcp ? (
          <div className="init-mcp-stage">
            <span>
              <small>Project MCP target</small>
              <code>{planQuery.data?.mcp_config.path ?? ".mcp.json"}</code>
            </span>
            <textarea
              className="init-mcp-editor"
              aria-label="Project MCP configuration"
              aria-invalid={mcpJsonError !== null}
              aria-describedby={mcpJsonError === null ? undefined : "init-mcp-error"}
              value={mcpJson}
              onChange={(event) => setMcpJson(event.target.value)}
              spellCheck={false}
            />
            {mcpJsonError !== null ? (
              <p id="init-mcp-error" className="init-error" role="alert">
                {mcpJsonError}
              </p>
            ) : null}
          </div>
        ) : null}
        {(planQuery.data?.warnings.length ?? 0) > 0 ? (
          <div className="init-warning-stack">
            {planQuery.data?.warnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        ) : null}
        <button
          type="button"
          className="init-primary-action"
          onClick={prepareApply}
          disabled={
            templateId === null ||
            selectedCount === 0 ||
            planQuery.data?.name_valid !== true ||
            mcpJsonError !== null ||
            initAction.phase === "preparing" ||
            initAction.phase === "executing"
          }
        >
          {initAction.phase === "preparing"
            ? "Preparing apply..."
            : initAction.phase === "executing"
              ? "Creating project..."
              : "Apply staged project"}
        </button>
        {initAction.jobId !== null ? <JobPane jobId={initAction.jobId} /> : null}
      </section>

      <ConfirmDialog action={initAction} actionTitle="Create project" />
    </div>
  );
}

function groupStagedFiles(files: InitStagedFile[]): Array<[string, InitStagedFile[]]> {
  const groups = new Map<string, InitStagedFile[]>();
  for (const file of files) {
    const group = groups.get(file.origin) ?? [];
    group.push(file);
    groups.set(file.origin, group);
  }
  return Array.from(groups.entries());
}

function TemplateButton({
  template,
  selected,
  onSelect,
}: {
  template: InitTemplate;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`init-template-card${selected ? " init-template-card--selected" : ""}`}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span>{template.label}</span>
      <StatePill
        variant={template.source === "github" ? "connecting" : "ok"}
        label={template.source}
      />
      <small>{template.description || template.url}</small>
    </button>
  );
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function validateMcpJson(value: string): string | null {
  try {
    const parsed: unknown = JSON.parse(value);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return "MCP configuration must be a JSON object.";
    }
    return null;
  } catch {
    return "MCP configuration contains invalid JSON.";
  }
}
