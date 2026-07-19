import { useState } from "react";
import type { ConfigTarget } from "@/api/config";
import { DeployTreePanel } from "@/modules/config-deploy/DeployTreePanel";

export function ConfigDeployModule() {
  const [target, setTarget] = useState<ConfigTarget>("claude");

  return (
    <div className="us3-module">
      <header className="us3-module__header">
        <div>
          <h1>Config Deployment</h1>
          <p>
            Review drift, inspect file diffs, and apply selected files through confirmed actions.
          </p>
        </div>
        <fieldset className="segmented-control config-target-switch">
          <legend className="visually-hidden">Deployment target</legend>
          {(["claude", "codex"] as ConfigTarget[]).map((item) => (
            <button
              key={item}
              type="button"
              className={target === item ? "is-active" : undefined}
              onClick={() => setTarget(item)}
            >
              {item}
            </button>
          ))}
        </fieldset>
      </header>

      <DeployTreePanel
        target={target}
        actionId={target === "codex" ? "codex.apply" : "config.apply"}
      />
    </div>
  );
}
