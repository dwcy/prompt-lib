// Grouped primary navigation: all 22 modules, six purpose groups, current selection highlighted.
import { useHealth } from "@/api/health";
import { NavBadges } from "@/components/shell/NavBadges";
import {
  MODULE_GROUP_LABELS,
  MODULE_GROUP_ORDER,
  MODULE_NAV_LABELS,
  MODULE_OPERATION_SUMMARIES,
  type ModuleKey,
  modulesByGroup,
} from "@/modules/registry";

export interface SidebarNavProps {
  activeModuleKey: ModuleKey;
  onSelectModule: (key: ModuleKey) => void;
}

export function SidebarNav({ activeModuleKey, onSelectModule }: SidebarNavProps) {
  const health = useHealth();
  const driftFlags = health.data?.drift_flags ?? null;

  return (
    <nav id="workspace-navigation" className="sidebar-nav select-none" aria-label="Primary">
      {MODULE_GROUP_ORDER.map((group) => {
        const modules = modulesByGroup(group);
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
    </nav>
  );
}
