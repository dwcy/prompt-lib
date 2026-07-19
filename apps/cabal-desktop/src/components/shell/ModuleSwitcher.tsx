import {
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useHealth } from "@/api/health";
import {
  MODULE_GROUP_LABELS,
  MODULE_GROUP_ORDER,
  MODULE_NAV_LABELS,
  MODULE_OPERATION_SUMMARIES,
  MODULE_REGISTRY,
  type ModuleDefinition,
  type ModuleKey,
} from "@/modules/registry";

const WORKSPACE_MODULES = MODULE_GROUP_ORDER.flatMap((group) =>
  MODULE_REGISTRY.filter((module) => module.group === group),
);

interface ModuleSwitcherProps {
  activeModuleKey: ModuleKey;
  onSelectModule: (key: ModuleKey) => void;
}

export function ModuleSwitcher({ activeModuleKey, onSelectModule }: ModuleSwitcherProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"all" | "attention">("all");
  const [activeIndex, setActiveIndex] = useState(0);
  const health = useHealth();
  const searchRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const closeSwitcher = useCallback(() => {
    setIsOpen(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  }, []);

  const attentionKeys = useMemo(() => {
    const keys = new Set<ModuleKey>();
    for (const entry of health.data?.modules ?? []) {
      if (entry.state !== "ok" && MODULE_REGISTRY.some((module) => module.key === entry.module)) {
        keys.add(entry.module as ModuleKey);
      }
    }
    if (health.isError) keys.add("diagnostics");
    if (health.data?.drift_flags?.claude === true) keys.add("config_deploy");
    if (health.data?.drift_flags?.codex === true) keys.add("codex");
    return keys;
  }, [health.data, health.isError]);

  const groups = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return MODULE_GROUP_ORDER.map((group) => ({
      group,
      modules: MODULE_REGISTRY.filter((module) => {
        if (module.group !== group) return false;
        if (view === "attention" && !attentionKeys.has(module.key)) return false;
        if (!normalizedQuery) return true;
        return [
          module.title,
          MODULE_NAV_LABELS[module.key],
          MODULE_OPERATION_SUMMARIES[module.key],
          MODULE_GROUP_LABELS[group],
        ]
          .join(" ")
          .toLowerCase()
          .includes(normalizedQuery);
      }),
    })).filter((entry) => entry.modules.length > 0);
  }, [attentionKeys, query, view]);

  const matches = groups.flatMap((entry) => entry.modules);
  const activeMatch = matches[activeIndex];

  useEffect(() => {
    function handleGlobalKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        if (event.repeat || event.isComposing) return;
        event.preventDefault();
        if (isOpen) closeSwitcher();
        else setIsOpen(true);
      }
      if (isOpen && event.key === "Escape") closeSwitcher();
    }
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [closeSwitcher, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    setQuery("");
    setView("all");
    setActiveIndex(
      Math.max(
        0,
        WORKSPACE_MODULES.findIndex((module) => module.key === activeModuleKey),
      ),
    );
    requestAnimationFrame(() => searchRef.current?.focus());
  }, [activeModuleKey, isOpen]);

  useEffect(() => {
    if (activeIndex < matches.length) return;
    setActiveIndex(Math.max(0, matches.length - 1));
  }, [activeIndex, matches.length]);

  useEffect(() => {
    if (view === "attention" && attentionKeys.size === 0) setView("all");
  }, [attentionKeys, view]);

  useEffect(() => {
    if (!isOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    dialogRef.current
      ?.querySelector<HTMLElement>(`[data-module-index="${activeIndex}"]`)
      ?.scrollIntoView?.({ block: "nearest" });
  }, [activeIndex, isOpen]);

  function selectModule(module: ModuleDefinition) {
    onSelectModule(module.key);
    closeSwitcher();
  }

  function handleSearchKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (matches.length === 0 ? 0 : (index + 1) % matches.length));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) =>
        matches.length === 0 ? 0 : (index - 1 + matches.length) % matches.length,
      );
    } else if (event.key === "Enter" && matches[activeIndex] !== undefined) {
      event.preventDefault();
      selectModule(matches[activeIndex]);
    }
  }

  function handleDialogKeyDown(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key !== "Tab") return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (focusable === undefined || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="module-switcher-trigger"
        onClick={() => setIsOpen(true)}
        aria-label="Find a Cabal module"
        aria-controls="cabal-module-switcher"
        aria-expanded={isOpen}
        title="Find a Cabal module"
      >
        Find
      </button>

      {isOpen ? (
        <div className="module-switcher-overlay">
          <button
            type="button"
            className="module-switcher-overlay__backdrop"
            aria-label="Close module switcher"
            onClick={closeSwitcher}
          />
          <section
            ref={dialogRef}
            id="cabal-module-switcher"
            className="module-switcher"
            role="dialog"
            aria-modal="true"
            aria-labelledby="module-switcher-title"
            onKeyDown={handleDialogKeyDown}
          >
            <header className="module-switcher__header">
              <div>
                <span>Workspace map</span>
                <strong id="module-switcher-title">Cabal control surface</strong>
              </div>
              <button
                type="button"
                className="module-switcher__close"
                onClick={closeSwitcher}
                aria-label="Close module switcher"
                title="Close"
              >
                x
              </button>
            </header>

            <input
              ref={searchRef}
              className="module-switcher__search"
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActiveIndex(0);
              }}
              onKeyDown={handleSearchKeyDown}
              placeholder="Search modules and operational areas"
              aria-label="Search Cabal modules"
              aria-controls="module-switcher-results"
              aria-activedescendant={
                activeMatch === undefined ? undefined : `module-switcher-result-${activeMatch.key}`
              }
            />
            <span className="module-switcher__sr-only" aria-live="polite">
              {matches.length} {matches.length === 1 ? "module" : "modules"} available
            </span>

            <fieldset className="module-switcher__modebar">
              <legend className="module-switcher__sr-only">Module view</legend>
              <button
                type="button"
                className={view === "all" ? "is-active" : undefined}
                aria-pressed={view === "all"}
                onClick={() => setView("all")}
              >
                All {MODULE_REGISTRY.length}
              </button>
              <button
                type="button"
                className={view === "attention" ? "is-active" : undefined}
                aria-pressed={view === "attention"}
                onClick={() => setView("attention")}
                disabled={attentionKeys.size === 0}
              >
                Attention {attentionKeys.size}
              </button>
            </fieldset>

            <div id="module-switcher-results" className="module-switcher__groups">
              {groups.length === 0 ? (
                <p className="module-switcher__empty">No module matches this search.</p>
              ) : (
                groups.map((entry) => (
                  <section
                    key={entry.group}
                    className={`module-switcher__group module-switcher__group--${entry.group}`}
                  >
                    <h3>
                      <span>{MODULE_GROUP_LABELS[entry.group]}</span>
                      <small>{entry.modules.length}</small>
                    </h3>
                    <div className="module-switcher__items">
                      {entry.modules.map((module) => {
                        const index = matches.findIndex((match) => match.key === module.key);
                        const isCurrent = module.key === activeModuleKey;
                        const moduleHealth = health.data?.modules.find(
                          (entry) => entry.module === module.key,
                        );
                        const hasDrift =
                          (module.key === "config_deploy" &&
                            health.data?.drift_flags?.claude === true) ||
                          (module.key === "codex" && health.data?.drift_flags?.codex === true);
                        const backendOffline = health.isError && module.key === "diagnostics";
                        const needsAttention =
                          backendOffline ||
                          (moduleHealth !== undefined && moduleHealth.state !== "ok");
                        return (
                          <button
                            key={module.key}
                            id={`module-switcher-result-${module.key}`}
                            data-module-index={index}
                            type="button"
                            className={`module-switcher__item${index === activeIndex ? " is-focused" : ""}${isCurrent ? " is-current" : ""}`}
                            aria-current={isCurrent ? "page" : undefined}
                            onMouseEnter={() => setActiveIndex(index)}
                            onClick={() => selectModule(module)}
                          >
                            <span>
                              <strong>{MODULE_NAV_LABELS[module.key]}</strong>
                              <small>{MODULE_OPERATION_SUMMARIES[module.key]}</small>
                            </span>
                            <span className="module-switcher__signals">
                              {hasDrift ? (
                                <em className="is-drift" title="Source and deployed config differ">
                                  Drift
                                </em>
                              ) : null}
                              {needsAttention ? (
                                <em
                                  className={`is-health is-${backendOffline ? "failed" : moduleHealth?.state}`}
                                  title={
                                    backendOffline
                                      ? "Backend connection unavailable"
                                      : moduleHealth?.detail || moduleHealth?.state
                                  }
                                >
                                  {backendOffline ? "offline" : moduleHealth?.state}
                                </em>
                              ) : null}
                              {isCurrent ? <em className="is-current">Current</em> : null}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </section>
                ))
              )}
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
