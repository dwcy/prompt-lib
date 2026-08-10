// Curated/System segmented pill switcher + variable search field for the environment toolbar.
import type { EnvScope } from "@/api/securityEnvironment";

export interface EnvScopeSwitcherProps {
  scope: EnvScope;
  onScopeChange: (scope: EnvScope) => void;
  queryText: string;
  onQueryChange: (value: string) => void;
  platform: string;
}

export function EnvScopeSwitcher({
  scope,
  onScopeChange,
  queryText,
  onQueryChange,
  platform,
}: EnvScopeSwitcherProps) {
  return (
    <div className="env-toolbar">
      <div className="env-toolbar__pills" role="tablist" aria-label="Environment scope">
        <button
          type="button"
          role="tab"
          aria-selected={scope === "curated"}
          className={scope === "curated" ? "is-active" : ""}
          onClick={() => onScopeChange("curated")}
        >
          Curated
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={scope === "system"}
          className={scope === "system" ? "is-active" : ""}
          onClick={() => onScopeChange("system")}
        >
          System
        </button>
      </div>
      <input
        type="search"
        value={queryText}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Find a variable"
        aria-label="Find an environment variable"
      />
      <span className="env-toolbar__platform">{platform}</span>
    </div>
  );
}
