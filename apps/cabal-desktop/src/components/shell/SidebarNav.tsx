// Grouped primary navigation (console redesign): brand lockup, ⌘K search trigger, all 22 modules
// in five purpose groups, and a mono workspace footer (current branch, project path, backend origin).
import { useHealth } from "@/api/health";
import cabalLogo from "@/assets/cabal-logo.png";
import { ModuleSwitcher } from "@/components/shell/ModuleSwitcher";
import { NavBadges } from "@/components/shell/NavBadges";
import { resolveApiUrl } from "@/lib/runtimeConfig";
import {
  MODULE_GROUP_LABELS,
  MODULE_GROUP_ORDER,
  MODULE_NAV_LABELS,
  MODULE_OPERATION_SUMMARIES,
  type ModuleKey,
  modulesByGroup,
} from "@/modules/registry";
import { useProjectContextStore } from "@/stores/projectContext";

export interface SidebarNavProps {
  activeModuleKey: ModuleKey;
  onSelectModule: (key: ModuleKey) => void;
}

export function SidebarNav({ activeModuleKey, onSelectModule }: SidebarNavProps) {
  const health = useHealth();
  const driftFlags = health.data?.drift_flags ?? null;
  const selectedProject = useProjectContextStore((state) => state.selected);
  const backendOrigin = originOf(resolveApiUrl("/api/health"));

  return (
    <nav id="workspace-navigation" className="sidebar-nav select-none" aria-label="Primary">
      <div className="sidebar-nav__brand">
        <img src={cabalLogo} alt="" aria-hidden="true" width={28} height={28} />
        <div>
          <strong>Cabal</strong>
          <span>local control surface</span>
        </div>
      </div>
      <ModuleSwitcher activeModuleKey={activeModuleKey} onSelectModule={onSelectModule} />
      <div className="sidebar-nav__groups">
        {MODULE_GROUP_ORDER.map((group) => {
          const modules = modulesByGroup(group);
          if (modules.length === 0) return null;
          return (
            <section key={group} className="sidebar-nav__group" data-group={group}>
              <header className="sidebar-nav__group-header">
                <h2 className="sidebar-nav__group-title">{MODULE_GROUP_LABELS[group]}</h2>
                <span className="sidebar-nav__group-count">{modules.length}</span>
              </header>
              <ul className="sidebar-nav__list">
                {modules.map((module) => {
                  const isActive = module.key === activeModuleKey;
                  const moduleHealth = health.data?.modules.find(
                    (entry) => entry.module === module.key,
                  );
                  return (
                    <li key={module.key}>
                      <button
                        type="button"
                        className={`sidebar-nav__item${isActive ? " sidebar-nav__item--active" : ""}`}
                        aria-label={module.title}
                        aria-current={isActive ? "page" : undefined}
                        title={MODULE_OPERATION_SUMMARIES[module.key]}
                        onClick={() => onSelectModule(module.key)}
                      >
                        <span className="sidebar-nav__item-dot" aria-hidden="true" />
                        <span className="sidebar-nav__item-label">
                          {MODULE_NAV_LABELS[module.key]}
                        </span>
                        <span className="sidebar-nav__badges">
                          <NavBadges
                            moduleKey={module.key}
                            driftFlags={driftFlags}
                            healthState={
                              health.isError && module.key === "diagnostics"
                                ? "failed"
                                : (moduleHealth?.state ?? null)
                            }
                            healthDetail={
                              health.isError && module.key === "diagnostics"
                                ? "Backend connection unavailable"
                                : (moduleHealth?.detail ?? null)
                            }
                          />
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>
      <footer className="sidebar-nav__footer">
        {health.data?.project_branch ? (
          <span title={health.data.project_branch}>⎇ {health.data.project_branch}</span>
        ) : null}
        {selectedProject ? <span title={selectedProject.path}>{selectedProject.path}</span> : null}
        <span>{backendOrigin} · cabal-web.v2</span>
      </footer>
    </nav>
  );
}

function originOf(url: string): string {
  try {
    return new URL(url, window.location.href).host || "127.0.0.1";
  } catch {
    return "127.0.0.1";
  }
}
