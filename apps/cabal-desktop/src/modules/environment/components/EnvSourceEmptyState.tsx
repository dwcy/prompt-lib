// The non-happy states of one source, plus the Azure link editor.
//
// `empty` and `degraded` never share wording: "nothing configured" and "only partly readable"
// are different claims, and collapsing them into "no data" is exactly the ambiguity FR-037
// exists to remove. See the copy table in the feature's quickstart.md.
import { useState } from "react";
import type { VariableSource } from "@/api/envSources";

export interface EnvSourceEmptyStateProps {
  source: VariableSource;
}

export function EnvSourceEmptyState({ source }: EnvSourceEmptyStateProps) {
  if (source.state === "degraded") {
    return (
      <div className="env-sources__notice" data-state="degraded" role="status">
        <p className="env-sources__notice-title">{source.label} is only partly readable.</p>
        <p className="env-sources__notice-body">{source.hint}</p>
      </div>
    );
  }
  return (
    <div className="env-sources__notice" data-state="empty" role="status">
      <p className="env-sources__notice-title">Nothing configured here.</p>
      <p className="env-sources__notice-body">
        {source.label} is reachable and signed in — it just holds no variables for this project.
      </p>
    </div>
  );
}

export interface AzureLinkEditorProps {
  source: VariableSource;
  isBusy: boolean;
  onRecord: (subscriptionId: string, resourceGroup: string) => void;
  onClear: () => void;
}

export function AzureLinkEditor({ source, isBusy, onRecord, onClear }: AzureLinkEditorProps) {
  const [subscriptionId, setSubscriptionId] = useState("");
  const [resourceGroup, setResourceGroup] = useState("");
  const isExplicit = source.link_confidence === "explicit";

  return (
    <form
      className="env-sources__link-editor"
      onSubmit={(event) => {
        event.preventDefault();
        onRecord(subscriptionId.trim(), resourceGroup.trim());
      }}
    >
      <p className="env-sources__link-reason">
        <span className="env-sources__link-label">Linked by</span>
        {source.link_reason ?? "an unstated signal"}
      </p>
      <div className="env-sources__link-fields">
        <label>
          Subscription
          <input
            type="text"
            value={subscriptionId}
            onChange={(event) => setSubscriptionId(event.target.value)}
            placeholder="subscription id"
            spellCheck={false}
            autoComplete="off"
          />
        </label>
        <label>
          Resource group
          <input
            type="text"
            value={resourceGroup}
            onChange={(event) => setResourceGroup(event.target.value)}
            placeholder="optional"
            spellCheck={false}
            autoComplete="off"
          />
        </label>
        <button type="submit" disabled={isBusy || subscriptionId.trim() === ""}>
          Record scope
        </button>
        <button type="button" onClick={onClear} disabled={isBusy || !isExplicit}>
          Clear
        </button>
      </div>
    </form>
  );
}
