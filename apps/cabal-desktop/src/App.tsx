// Root workspace shell: grouped navigation, health strip, module outlet, and the schema-refresh
// prompt. Gates the workspace behind the Project Gate (T032) until a project has been explicitly
// selected — see useProjectContextSync's doc comment for what "explicitly selected" means.
import { useEffect, useState } from "react";
import { onSchemaMismatch } from "@/api/errors";
import { HealthStrip } from "@/components/shell/HealthStrip";
import { ModuleOutlet } from "@/components/shell/ModuleOutlet";
import { SidebarNav } from "@/components/shell/SidebarNav";
import { useProjectContextSync } from "@/hooks/useProjectContextSync";
import { ProjectGateModule } from "@/modules/project-gate/ProjectGateModule";
import { DEFAULT_MODULE_KEY } from "@/modules/registry";
import { useProjectContextStore } from "@/stores/projectContext";
import { useUiPrefsStore } from "@/stores/uiPrefs";

const APP_NAME = "Cabal";

export default function App() {
  // Single source of truth for the active module (was local useState mirroring the store's
  // initial value only): deriving directly from uiPrefsStore lets any module — not just
  // SidebarNav — navigate the shell, which Overview's deep links (T033) rely on.
  const lastModule = useUiPrefsStore((state) => state.lastModule);
  const setLastModule = useUiPrefsStore((state) => state.setLastModule);
  const sidebarCollapsed = useUiPrefsStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiPrefsStore((state) => state.toggleSidebar);
  const activeModuleKey = lastModule ?? DEFAULT_MODULE_KEY;
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
    return (
      <main className="app-shell app-shell--gate">
        <header className="app-shell__header">
          <h1 className="app-shell__title select-none">{APP_NAME}</h1>
          <HealthStrip />
        </header>
        <div className="app-shell__gate-body">
          <ProjectGateModule />
        </div>
      </main>
    );
  }

  return (
    <div className={`app-shell${sidebarCollapsed ? " app-shell--sidebar-collapsed" : ""}`}>
      <header className="app-shell__header">
        <h1 className="app-shell__title select-none">{APP_NAME}</h1>
        <button
          type="button"
          className="app-shell__sidebar-toggle select-none"
          onClick={toggleSidebar}
        >
          {sidebarCollapsed ? "Expand" : "Collapse"}
        </button>
        <HealthStrip />
      </header>
      <div className="app-shell__body">
        <SidebarNav activeModuleKey={activeModuleKey} onSelectModule={setLastModule} />
        <main className="app-shell__content">
          <ModuleOutlet activeModuleKey={activeModuleKey} />
        </main>
      </div>
    </div>
  );
}
