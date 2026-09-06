// Search field and platform marker for the built-in Curated/System views.
//
// The Curated/System pills this component used to own were replaced by the module's tab strip
// (EnvSourceTabs), where they are now the first two of a dynamic set — the switcher keeps only
// the controls that belong to the built-in scopes themselves.
export interface EnvScopeSwitcherProps {
  queryText: string;
  onQueryChange: (value: string) => void;
  platform: string;
}

export function EnvScopeSwitcher({ queryText, onQueryChange, platform }: EnvScopeSwitcherProps) {
  return (
    <div className="env-toolbar">
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
