// Grouped primary navigation: all 22 modules, six purpose groups, current selection highlighted.
import { MODULE_GROUP_LABELS, MODULE_GROUP_ORDER, modulesByGroup } from "@/modules/registry";

export interface SidebarNavProps {
  activeModuleKey: string;
  onSelectModule: (key: string) => void;
}

export function SidebarNav({ activeModuleKey, onSelectModule }: SidebarNavProps) {
  return (
    <nav className="sidebar-nav select-none" aria-label="Primary">
      {MODULE_GROUP_ORDER.map((group) => (
        <section key={group} className="sidebar-nav__group">
          <h2 className="sidebar-nav__group-title">{MODULE_GROUP_LABELS[group]}</h2>
          <ul className="sidebar-nav__list">
            {modulesByGroup(group).map((module) => {
              const isActive = module.key === activeModuleKey;
              return (
                <li key={module.key}>
                  <button
                    type="button"
                    className={`sidebar-nav__item${isActive ? " sidebar-nav__item--active" : ""}`}
                    aria-current={isActive ? "page" : undefined}
                    onClick={() => onSelectModule(module.key)}
                  >
                    {module.title}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </nav>
  );
}
