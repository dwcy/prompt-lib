// The deploy tree itself: one section per config component, each file with its drift state, a
// queue checkbox, and the two ways to read it — the diff, or the whole file.
import type { ConfigComponent, ConfigFile } from "@/api/config";
import { StatePill } from "@/components/StatePill";
import { fileStateVariant } from "./deployPresentation";

export interface DeployComponentTreeProps {
  components: ConfigComponent[];
  selectedPaths: Set<string>;
  onToggleFile: (relPath: string, checked: boolean) => void;
  onToggleComponent: (files: ConfigFile[], checked: boolean) => void;
  onShowDiff: (relPath: string) => void;
  onViewFile: (file: ConfigFile) => void;
}

export function DeployComponentTree({
  components,
  selectedPaths,
  onToggleFile,
  onToggleComponent,
  onShowDiff,
  onViewFile,
}: DeployComponentTreeProps) {
  return (
    <section className="cfg-deploy__tree">
      {components.map((component) => {
        const files = component.files;
        const selectedInComponent = files.filter((file) => selectedPaths.has(file.rel_path)).length;
        const changedInComponent = files.filter((file) => file.state === "changed").length;
        const newInComponent = files.filter((file) => file.state === "new").length;
        const checked = files.length > 0 && selectedInComponent === files.length;
        const indeterminate = selectedInComponent > 0 && selectedInComponent < files.length;

        return (
          <article key={component.key} className="cfg-deploy__component">
            <label className="cfg-deploy__component-header">
              <input
                type="checkbox"
                checked={checked}
                ref={(node) => {
                  if (node !== null) node.indeterminate = indeterminate;
                }}
                onChange={(event) => onToggleComponent(files, event.target.checked)}
              />
              <span className="cfg-deploy__component-title-block">
                <span className="cfg-deploy__component-title">{component.label}</span>
                <span className="cfg-deploy__component-group">{component.group}</span>
              </span>
              <span className="cfg-deploy__component-rollup">
                {changedInComponent} changed · {newInComponent} new · {selectedInComponent} queued
              </span>
            </label>

            <ul className="cfg-deploy__file-list">
              {files.map((file) => (
                <li key={file.rel_path} className="cfg-deploy__file-item">
                  <label className="cfg-deploy__file-select">
                    <input
                      type="checkbox"
                      checked={selectedPaths.has(file.rel_path)}
                      disabled={file.state === "unchanged"}
                      onChange={(event) => onToggleFile(file.rel_path, event.target.checked)}
                    />
                    <span className="cfg-deploy__file-path">{file.rel_path}</span>
                  </label>
                  <StatePill variant={fileStateVariant(file.state)} label={file.state} />
                  <button
                    type="button"
                    className="cfg-deploy__file-diff-btn"
                    onClick={() => onShowDiff(file.rel_path)}
                    disabled={!file.diff_available}
                  >
                    Diff
                  </button>
                  <button
                    type="button"
                    className="cfg-deploy__file-view-btn"
                    onClick={() => onViewFile(file)}
                  >
                    View file
                  </button>
                </li>
              ))}
            </ul>
          </article>
        );
      })}
    </section>
  );
}
