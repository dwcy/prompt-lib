// Environment variables console. Curated and System remain the first two tabs, unchanged
// (FR-002); every tab after them is built from what the backend actually detected for the
// selected project (FR-005), and rebuilt whenever that project changes (FR-006).
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  useEnvSources,
  useRefreshSource,
  useRevealValue,
  type VariableEntry,
  type VariableSource,
} from "@/api/envSources";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { useAction } from "@/hooks/useAction";
import { BuiltInScope } from "@/modules/environment/BuiltInScope";
import {
  AzureLinkEditor,
  EnvSourceEmptyState,
} from "@/modules/environment/components/EnvSourceEmptyState";
import { EnvSourceTable, entryKey } from "@/modules/environment/components/EnvSourceTable";
import { type EnvSourceTab, EnvSourceTabs } from "@/modules/environment/components/EnvSourceTabs";
import type { RevealState } from "@/modules/environment/components/RevealCell";
import { useProjectContextStore } from "@/stores/projectContext";
import "./EnvironmentModule.css";

const BUILT_IN_TABS: EnvSourceTab[] = [
  {
    key: "curated",
    label: "Curated",
    qualifier: null,
    state: null,
    outsideRepository: false,
    linkConfidence: null,
    linkReason: null,
    count: 0,
  },
  {
    key: "system",
    label: "System",
    qualifier: null,
    state: null,
    outsideRepository: false,
    linkConfidence: null,
    linkReason: null,
    count: 0,
  },
];

const AZURE_SOURCE_IDS = new Set(["azure_keyvault", "azure_app_settings"]);

export function EnvironmentModule() {
  const queryClient = useQueryClient();
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  const [activeTab, setActiveTab] = useState<string>("curated");
  // A source refreshed on its own replaces just itself, so waiting 40s on Azure never
  // re-runs — or discards — the sources that already loaded.
  const [refreshedSources, setRefreshedSources] = useState<Record<string, VariableSource>>({});
  // Revealed values live here and nowhere else — never in the query cache, which would
  // survive the tab and project changes FR-014 requires them not to.
  const [revealed, setRevealed] = useState<Record<string, RevealState>>({});
  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const sourcesQuery = useEnvSources();
  const revealMutation = useRevealValue();
  const refreshSource = useRefreshSource();
  const azureLinkAction = useAction("env.azure_link.set");

  const sources = (sourcesQuery.data?.sources ?? []).map(
    (source) => refreshedSources[source.id] ?? source,
  );
  const activeSource = sources.find((source) => source.id === activeTab) ?? null;

  // FR-014: a tab change or a project change re-masks everything, with no user action.
  // Both deps are triggers rather than values the body reads; dropping them would leave
  // revealed values on screen across exactly the two transitions that must re-mask them.
  // biome-ignore lint/correctness/useExhaustiveDependencies: trigger-only deps, see above
  useEffect(() => {
    setRevealed({});
    setPendingKey(null);
  }, [activeTab, projectPath]);

  // A refreshed source belongs to the project it was fetched for and must not survive a switch.
  // biome-ignore lint/correctness/useExhaustiveDependencies: trigger-only dep, see above
  useEffect(() => {
    setRefreshedSources({});
  }, [projectPath]);

  // The new project's tabs have not arrived yet, so selection falls back to one that exists.
  // biome-ignore lint/correctness/useExhaustiveDependencies: trigger-only dep, see above
  useEffect(() => {
    setActiveTab("curated");
  }, [projectPath]);

  useEffect(() => {
    if (azureLinkAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({
      queryKey: queryKeys.scoped("envSources", projectPath),
    });
  }, [azureLinkAction.phase, queryClient, projectPath]);

  const tabs = useMemo(() => [...BUILT_IN_TABS, ...sources.map(sourceTab)], [sources]);

  // A tab can disappear when the project changes or a source stops being detected; falling
  // back keeps the module usable instead of rendering a panel for a tab that no longer exists.
  useEffect(() => {
    if (!tabs.some((tab) => tab.key === activeTab)) setActiveTab("curated");
  }, [tabs, activeTab]);

  function handleReveal(entry: VariableEntry) {
    const key = entryKey(entry);
    setPendingKey(key);
    revealMutation.mutate(
      { source_id: entry.source_id, container_id: entry.container_id, name: entry.name },
      {
        onSettled: () => setPendingKey(null),
        onSuccess: (result) =>
          setRevealed((current) => ({
            ...current,
            [key]: {
              status: result.status,
              value: result.value,
              reason: result.reason,
              isReference: result.is_reference,
            },
          })),
        onError: (error) =>
          setRevealed((current) => ({
            ...current,
            [key]: {
              status: "unavailable",
              value: null,
              reason: error.message,
              isReference: false,
            },
          })),
      },
    );
  }

  function handleMask(entry: VariableEntry) {
    setRevealed((current) => {
      const next = { ...current };
      delete next[entryKey(entry)];
      return next;
    });
  }

  const isBuiltIn = activeTab === "curated" || activeTab === "system";

  return (
    <div className="env-console">
      <EnvSourceTabs tabs={tabs} activeKey={activeTab} onSelect={setActiveTab} />

      {sourcesQuery.isError ? (
        <p className="inline-error">
          Source discovery is unavailable: {sourcesQuery.error.message}
        </p>
      ) : null}

      {isBuiltIn ? (
        <BuiltInScope scope={activeTab} />
      ) : (
        <div
          className="env-sources__panel"
          role="tabpanel"
          id={`env-panel-${activeTab}`}
          aria-labelledby={`env-tab-${activeTab}`}
        >
          {activeSource === null ? (
            <EmptyState title="Loading sources..." animated />
          ) : (
            <SourcePanel
              source={activeSource}
              revealed={revealed}
              pendingKey={pendingKey}
              isRefreshing={sourcesQuery.isFetching || refreshSource.isPending}
              onRefresh={() =>
                refreshSource.mutate(activeSource.id, {
                  onSuccess: (source) => {
                    if (source === null) return;
                    setRefreshedSources((current) => ({ ...current, [source.id]: source }));
                  },
                })
              }
              onReveal={handleReveal}
              onMask={handleMask}
              azureLinkAction={azureLinkAction}
            />
          )}
        </div>
      )}

      {sourcesQuery.data !== undefined && sourcesQuery.data.notices.length > 0 ? (
        <ul className="env-sources__notices">
          {sourcesQuery.data.notices.map((notice) => (
            <li key={notice}>{notice}</li>
          ))}
        </ul>
      ) : null}

      <ConfirmDialog action={azureLinkAction} actionTitle="Record Azure scope" />
    </div>
  );
}

function SourcePanel({
  source,
  revealed,
  pendingKey,
  isRefreshing,
  onRefresh,
  onReveal,
  onMask,
  azureLinkAction,
}: {
  source: VariableSource;
  revealed: Record<string, RevealState>;
  pendingKey: string | null;
  isRefreshing: boolean;
  onRefresh: () => void;
  onReveal: (entry: VariableEntry) => void;
  onMask: (entry: VariableEntry) => void;
  azureLinkAction: ReturnType<typeof useAction>;
}) {
  const hasEntries = source.containers.some((container) => container.entries.length > 0);
  return (
    <>
      <div className="env-intro">
        <span className="env-intro__text">
          Names only. Use the eye on a row to fetch that one value.
        </span>
        <span className="env-intro__summary">{summarise(source)}</span>
        <RefreshButton label={source.label} onRefresh={onRefresh} isFetching={isRefreshing} />
      </div>

      {AZURE_SOURCE_IDS.has(source.id) ? (
        <AzureLinkEditor
          source={source}
          isBusy={azureLinkAction.phase === "preparing"}
          onRecord={(subscriptionId, resourceGroup) =>
            azureLinkAction.prepare({
              subscription_id: subscriptionId,
              resource_group: resourceGroup === "" ? null : resourceGroup,
            })
          }
          onClear={() => azureLinkAction.prepare({ subscription_id: null, resource_group: null })}
        />
      ) : null}

      {source.state === "degraded" || !hasEntries ? (
        <EnvSourceEmptyState source={source} />
      ) : (
        <EnvSourceTable
          containers={source.containers}
          revealed={revealed}
          pendingKey={pendingKey}
          onReveal={onReveal}
          onMask={onMask}
        />
      )}
    </>
  );
}

function summarise(source: VariableSource): string {
  const count = source.containers.reduce((total, container) => total + container.entries.length, 0);
  if (source.state === "degraded") return "partly readable";
  return `${count} ${count === 1 ? "name" : "names"}`;
}

function sourceTab(source: VariableSource): EnvSourceTab {
  const [first] = source.containers;
  return {
    key: source.id,
    label: source.label,
    qualifier: first?.qualifier ?? null,
    state: source.state,
    outsideRepository: source.outside_repository,
    linkConfidence: source.link_confidence,
    linkReason: source.link_reason,
    count: source.containers.reduce((total, container) => total + container.entries.length, 0),
  };
}
