// Root workspace shell: grouped navigation, health strip, module outlet, and the schema-refresh
// prompt. Gates the workspace behind the Project Gate (T032) until a project has been explicitly
// selected — see useProjectContextSync's doc comment for what "explicitly selected" means.
import { useEffect, useState } from "react";
import { onSchemaMismatch } from "@/api/errors";
import { useHealth } from "@/api/health";
import { queryClient } from "@/api/queryClient";
import { HealthStrip } from "@/components/shell/HealthStrip";
import { JobTray } from "@/components/shell/JobTray";
import { ModuleOutlet } from "@/components/shell/ModuleOutlet";
import { SidebarNav } from "@/components/shell/SidebarNav";
import { useProjectContextSync } from "@/hooks/useProjectContextSync";
import { ProjectGateModule } from "@/modules/project-gate/ProjectGateModule";
import {
  DEFAULT_MODULE_KEY,
  findModule,
  MODULE_OPERATION_SUMMARIES,
  type ModuleKey,
  requireModule,
} from "@/modules/registry";
import { useProjectContextStore } from "@/stores/projectContext";
import { useUiPrefsStore } from "@/stores/uiPrefs";

const APP_NAME = "Cabal";
const PROJECT_ENTRY_MODULES = new Set<ModuleKey>(["project_gate", "provider", "init_wizard"]);

export default function App() {
  // Single source of truth for the active module (was local useState mirroring the store's
  // initial value only): deriving directly from uiPrefsStore lets any module — not just
  // SidebarNav — navigate the shell, which Overview's deep links (T033) rely on.
  const lastModule = useUiPrefsStore((state) => state.lastModule);
  const setLastModule = useUiPrefsStore((state) => state.setLastModule);
  const sidebarCollapsed = useUiPrefsStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiPrefsStore((state) => state.toggleSidebar);
  const setSidebarCollapsed = useUiPrefsStore((state) => state.setSidebarCollapsed);
  const requestedModuleKey = lastModule ?? DEFAULT_MODULE_KEY;
  const activeModule = findModule(requestedModuleKey) ?? requireModule(DEFAULT_MODULE_KEY);
  const activeModuleKey = activeModule.key;
  const [schemaMismatch, setSchemaMismatch] = useState<string | null>(null);
  const selectedProject = useProjectContextStore((state) => state.selected);
  useProjectContextSync();

  useEffect(() => onSchemaMismatch(setSchemaMismatch), []);

  if (schemaMismatch !== null) {
    return (
      <main className="app-shell app-shell--refresh-prompt" role="alert">
        <h1>{APP_NAME}</h1>
        <p>The backend now speaks schema {schemaMismatch}, which this window does not support.</p>
        <button type="button" onClick={() => window.location.reload()}>
          Refresh
        </button>
      </main>
    );
  }

  if (selectedProject === null) {
    const entryModuleKey = PROJECT_ENTRY_MODULES.has(activeModuleKey)
      ? activeModuleKey
      : "project_gate";
    return (
      <main className="app-shell app-shell--gate">
        <a className="skip-link" href="#project-entry-content">
          Skip to project options
        </a>
        <header className="app-shell__header">
          <BrandLockup />
          <HealthStrip />
        </header>
        <div className="app-shell__gate-body">
          <nav className="project-entry-nav" aria-label="Project entry">
            <button
              type="button"
              className={entryModuleKey === "project_gate" ? "is-active" : undefined}
              onClick={() => setLastModule("project_gate")}
            >
              Open existing
            </button>
            <button
              type="button"
              className={entryModuleKey === "provider" ? "is-active" : undefined}
              onClick={() => setLastModule("provider")}
            >
              Clone repository
            </button>
            <button
              type="button"
              className={entryModuleKey === "init_wizard" ? "is-active" : undefined}
              onClick={() => setLastModule("init_wizard")}
            >
              Create new
            </button>
          </nav>
          <div id="project-entry-content" className="app-shell__gate-view" tabIndex={-1}>
            {entryModuleKey === "project_gate" ? (
              <ProjectGateModule />
            ) : (
              <ModuleOutlet activeModuleKey={entryModuleKey} />
            )}
          </div>
        </div>
      </main>
    );
  }

  function selectModule(key: ModuleKey) {
    setLastModule(key);
    if (
      typeof window.matchMedia === "function" &&
      window.matchMedia("(max-width: 768px)").matches
    ) {
      setSidebarCollapsed(true);
    }
  }

  return (
    <div
      className={`app-shell${sidebarCollapsed ? " app-shell--sidebar-collapsed" : ""}`}
      data-module-group={activeModule.group}
    >
      <a className="skip-link" href="#workspace-content">
        Skip to workspace
      </a>
      <SidebarNav activeModuleKey={activeModuleKey} onSelectModule={selectModule} />
      <div className="app-shell__main">
        <header className="app-shell__header">
          <button
            type="button"
            className="app-shell__sidebar-toggle select-none"
            onClick={toggleSidebar}
            aria-label={sidebarCollapsed ? "Expand navigation" : "Collapse navigation"}
            aria-expanded={!sidebarCollapsed}
            aria-controls="workspace-navigation"
            title={sidebarCollapsed ? "Expand navigation" : "Collapse navigation"}
          >
            <span aria-hidden="true">{sidebarCollapsed ? "›" : "‹"}</span>
          </button>
          <h1
            className="app-shell__view-title select-none"
            title={MODULE_OPERATION_SUMMARIES[activeModule.key]}
          >
            {activeModule.title}
          </h1>
          <SnapshotStamp />
          <div className="app-shell__header-spacer" />
          <HealthStrip />
          <button
            type="button"
            className="app-shell__refresh"
            onClick={() => void queryClient.invalidateQueries()}
            title="Refetch every visible data source"
          >
            Refresh
          </button>
          <button
            type="button"
            className="app-shell__project-context"
            onClick={() => selectModule("project_gate")}
            title="Switch project"
          >
            <span>{selectedProject.name}</span>
            <small>{selectedProject.path}</small>
          </button>
          <JobTray />
        </header>
        <main id="workspace-content" className="app-shell__content" tabIndex={-1}>
          <ModuleOutlet activeModuleKey={activeModuleKey} />
        </main>
      </div>
    </div>
  );
}

function BrandLockup() {
  return (
    <div className="app-shell__brand select-none">
      <span className="app-shell__brand-mark" aria-hidden="true">
        C
      </span>
      <h1>{APP_NAME}</h1>
    </div>
  );
}

function SnapshotStamp() {
  // Last successful /api/health fetch — the freshest moment the workspace data is known-good.
  const health = useHealth();
  if (health.dataUpdatedAt === 0) return null;
  const stamp = new Date(health.dataUpdatedAt).toISOString().slice(11, 19);
  return (
    <span className="app-shell__snapshot select-none" title="Last successful backend snapshot">
      snapshot {stamp}Z
    </span>
  );
}
