// Root workspace shell: grouped navigation, health strip, module outlet, and the schema-refresh prompt.
import { useEffect, useState } from "react";
import { onSchemaMismatch } from "@/api/errors";
import { HealthStrip } from "@/components/shell/HealthStrip";
import { ModuleOutlet } from "@/components/shell/ModuleOutlet";
import { SidebarNav } from "@/components/shell/SidebarNav";
import { DEFAULT_MODULE_KEY } from "@/modules/registry";
import { useUiPrefsStore } from "@/stores/uiPrefs";

const APP_NAME = "Cabal";

export default function App() {
  const lastModule = useUiPrefsStore((state) => state.lastModule);
  const setLastModule = useUiPrefsStore((state) => state.setLastModule);
  const sidebarCollapsed = useUiPrefsStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiPrefsStore((state) => state.toggleSidebar);
  const [activeModuleKey, setActiveModuleKey] = useState(lastModule ?? DEFAULT_MODULE_KEY);
  const [schemaMismatch, setSchemaMismatch] = useState<string | null>(null);

  useEffect(() => onSchemaMismatch(setSchemaMismatch), []);

  function selectModule(key: string): void {
    setActiveModuleKey(key);
    setLastModule(key);
  }

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
        <SidebarNav activeModuleKey={activeModuleKey} onSelectModule={selectModule} />
        <main className="app-shell__content">
          <ModuleOutlet activeModuleKey={activeModuleKey} />
        </main>
      </div>
    </div>
  );
}
