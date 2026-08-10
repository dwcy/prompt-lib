import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  type LocalConfigAction,
  useCodexConversion,
  useCodexLocalConfig,
  useConfigTree,
} from "@/api/config";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { StatePill } from "@/components/StatePill";
import { VirtualDataTable, type VirtualDataTableColumn } from "@/components/VirtualDataTable";
import { useAction } from "@/hooks/useAction";
import { DeployTreePanel } from "@/modules/config-deploy/DeployTreePanel";
import { useProjectContextStore } from "@/stores/projectContext";
import "./CodexModule.css";

type SelectionState = Record<string, Set<string>>;
type ConversionState = "converted" | "not-converted" | "codex-only" | "stale" | "unsupported";
type ConversionRow = {
  asset: string;
  state: ConversionState;
  kind: string;
  source_path: string | null;
  output_path: string | null;
  reason: string;
};

export function CodexModule() {
  const queryClient = useQueryClient();
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  const [template, setTemplate] = useState<string | null>(null);
  const [selection, setSelection] = useState<SelectionState>({});
  const [conversionFilter, setConversionFilter] = useState<ConversionState | "all">("all");
  const [pendingTitle, setPendingTitle] = useState("Apply Codex local config");
  const deployQuery = useConfigTree("codex");
  const conversionQuery = useCodexConversion();
  const localQuery = useCodexLocalConfig(template);
  const localAction = useAction("codex.local_apply");

  useEffect(() => {
    if (localAction.phase !== "succeeded") return;
    setSelection({});
    void queryClient.invalidateQueries({
      queryKey: queryKeys.scoped("localConfig", projectPath, "codex"),
    });
  }, [localAction.phase, queryClient, projectPath]);

  const conversionRows = conversionQuery.data?.rows ?? [];
  const conversionCounts = useMemo(() => countConversions(conversionRows), [conversionRows]);
  const visibleConversionRows = useMemo(
    () =>
      conversionFilter === "all"
        ? conversionRows
        : conversionRows.filter((row) => row.state === conversionFilter),
    [conversionFilter, conversionRows],
  );
  const localActions = localQuery.data?.actions ?? [];
  const localPending = localActions.filter((action) => action.applicable).length;
  const deployDrift =
    (deployQuery.data?.drift.changed_count ?? 0) + (deployQuery.data?.drift.new_count ?? 0);

  return (
    <div className="codex">
      <header className="codex__header">
        <div>
          <h1>Codex Parity</h1>
          <p>Deploy Codex assets, scaffold local agent files, and audit conversion coverage.</p>
        </div>
      </header>

      <section className="codex__runway">
        <div className="codex__runway-status">
          <span className="codex__eyebrow">Parity runway</span>
          <strong>
            {deployDrift + localPending + conversionCounts.attention === 0
              ? "Codex surface aligned"
              : `${deployDrift + localPending + conversionCounts.attention} item(s) need attention`}
          </strong>
        </div>
        <ol className="codex__runway-steps" aria-label="Codex parity workflow">
          <li
            className={`codex__runway-step ${deployDrift === 0 ? "is-complete" : "is-current"}`}
          >
            <span className="codex__runway-step-index">01</span>
            <strong>Deploy shared assets</strong>
            <small className="codex__runway-step-meta">{deployDrift} drifted</small>
          </li>
          <li
            className={`codex__runway-step ${localPending === 0 ? "is-complete" : "is-current"}`}
          >
            <span className="codex__runway-step-index">02</span>
            <strong>Scaffold project</strong>
            <small className="codex__runway-step-meta">{localPending} pending</small>
          </li>
          <li
            className={`codex__runway-step ${
              conversionCounts.attention === 0 ? "is-complete" : "is-current"
            }`}
          >
            <span className="codex__runway-step-index">03</span>
            <strong>Audit translation</strong>
            <small className="codex__runway-step-meta">
              {conversionCounts.attention} exceptions
            </small>
          </li>
        </ol>
      </section>

      <section className="codex__section">
        <h2>Deploy Tree</h2>
        <DeployTreePanel target="codex" actionId="codex.apply" />
      </section>

      <section className="codex__section">
        <header className="codex__section-header">
          <h2>Local Scaffold</h2>
          <label className="codex__field">
            Template
            <select
              value={template ?? ""}
              onChange={(event) => {
                setTemplate(event.currentTarget.value || null);
                setSelection({});
              }}
            >
              <option value="">None</option>
              {(localQuery.data?.template_options ?? []).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </header>
        {localQuery.isPending ? (
          <EmptyState title="Loading Codex local plan..." />
        ) : localQuery.isError ? (
          <EmptyState title="Could not load Codex local plan" body={localQuery.error.message} />
        ) : (
          <div className="codex__scaffold-list">
            {localQuery.data.actions.map((item, index) => (
              <CodexLocalCard
                key={item.key}
                step={index + 1}
                action={item}
                selectedKeys={selectedKeysFor(item, selection)}
                onToggle={(itemKey, checked) =>
                  setSelection((current) => updateSelection(current, item, itemKey, checked))
                }
                onApply={() => {
                  const itemKeys = Array.from(selectedKeysFor(item, selection));
                  setPendingTitle(`Apply ${item.label}`);
                  localAction.prepare({ action: item.key, item_keys: itemKeys, template });
                }}
              />
            ))}
          </div>
        )}
      </section>

      <section className="codex__section">
        <header className="codex__section-header codex__audit-header">
          <div>
            <h2>Conversion Audit</h2>
            <p>
              {conversionCounts.converted} translated, {conversionCounts.attention} exceptions.
            </p>
          </div>
          <div className="codex__filters">
            {(
              ["all", "converted", "not-converted", "codex-only", "stale", "unsupported"] as const
            ).map((state) => (
              <button
                key={state}
                type="button"
                className={
                  conversionFilter === state ? "codex__filter-btn is-active" : "codex__filter-btn"
                }
                onClick={() => setConversionFilter(state)}
              >
                <span>{state}</span>
                <strong>
                  {state === "all" ? conversionRows.length : conversionCounts.byState[state]}
                </strong>
              </button>
            ))}
          </div>
        </header>
        {conversionQuery.data !== undefined ? <ConversionPipeline rows={conversionRows} /> : null}
        {conversionQuery.isPending ? (
          <EmptyState title="Loading conversion audit..." />
        ) : conversionQuery.isError ? (
          <EmptyState
            title="Could not load conversion audit"
            body={conversionQuery.error.message}
          />
        ) : (
          <div className="codex__ledger">
            <VirtualDataTable
              rows={visibleConversionRows}
              getRowId={(row) => row.asset}
              columns={conversionColumns}
              rowHeight={72}
              ariaLabel="Codex conversion routes"
              emptyMessage="No conversion routes match this state"
            />
          </div>
        )}
      </section>

      <ConfirmDialog
        isOpen={localAction.phase !== "idle" && localAction.phase !== "succeeded"}
        actionTitle={pendingTitle}
        ticket={localAction.ticket}
        phase={localAction.phase}
        reviewNotice={localAction.reviewNotice}
        error={localAction.error}
        onConfirm={localAction.confirm}
        onCancel={localAction.reset}
      />

      {localAction.jobId !== null ? <JobPane jobId={localAction.jobId} /> : null}
    </div>
  );
}

const conversionColumns: Array<VirtualDataTableColumn<ConversionRow>> = [
  {
    key: "asset",
    header: "Asset",
    render: (row) => (
      <span className="codex__cell-identity">
        <strong>{row.asset}</strong>
        <small>{row.kind}</small>
      </span>
    ),
    sortAccessor: (row) => row.asset,
  },
  {
    key: "route",
    header: "Translation route",
    render: (row) => (
      <span className="codex__cell-route">
        <span>
          <small>Claude source</small>
          <code>{row.source_path ?? "Codex native"}</code>
        </span>
        <i className="codex__cell-route-arrow" aria-hidden="true">
          -&gt;
        </i>
        <span>
          <small>Codex output</small>
          <code>{row.output_path ?? "No output"}</code>
        </span>
      </span>
    ),
    sortAccessor: (row) => row.source_path ?? "",
  },
  {
    key: "gate",
    header: "Conversion gate",
    render: (row) => (
      <span className="codex__cell-decision">
        <StatePill variant={conversionVariant(row.state)} label={row.state} />
        <small>{row.reason || conversionDecisionCopy(row.state)}</small>
      </span>
    ),
    sortAccessor: (row) => row.state,
  },
];

function ConversionPipeline({ rows }: { rows: ConversionRow[] }) {
  const sourced = rows.filter((row) => row.source_path !== null).length;
  const emitted = rows.filter((row) => row.output_path !== null).length;
  const native = rows.filter((row) => row.state === "codex-only").length;
  const converted = rows.filter((row) => row.state === "converted").length;
  const exceptions = rows.length - converted - native;

  return (
    <section className="codex__pipeline" aria-label="Codex conversion pipeline">
      <div className="codex__pipeline-stage">
        <span className="codex__pipeline-stage-index">01</span>
        <div>
          <small>Source inventory</small>
          <strong>{sourced} Claude assets</strong>
        </div>
      </div>
      <div className="codex__pipeline-connector">
        <span>{converted} translated</span>
        <i aria-hidden="true" />
      </div>
      <div className="codex__pipeline-stage" data-attention={exceptions > 0}>
        <span className="codex__pipeline-stage-index">02</span>
        <div>
          <small>Conversion gate</small>
          <strong>{exceptions === 0 ? "No exceptions" : `${exceptions} exceptions`}</strong>
        </div>
      </div>
      <div className="codex__pipeline-connector">
        <span>{native} Codex native</span>
        <i aria-hidden="true" />
      </div>
      <div className="codex__pipeline-stage">
        <span className="codex__pipeline-stage-index">03</span>
        <div>
          <small>Output inventory</small>
          <strong>{emitted} Codex assets</strong>
        </div>
      </div>
    </section>
  );
}

function CodexLocalCard({
  step,
  action,
  selectedKeys,
  onToggle,
  onApply,
}: {
  step: number;
  action: LocalConfigAction;
  selectedKeys: Set<string>;
  onToggle: (itemKey: string, checked: boolean) => void;
  onApply: () => void;
}) {
  const counts = countPreviewItems(action);

  return (
    <article className="codex__scaffold-stage">
      <span className="codex__scaffold-stage-number">{String(step).padStart(2, "0")}</span>
      <div className="codex__scaffold-card">
        <header className="codex__scaffold-card-header">
          <div>
            <h3>{action.label}</h3>
            <p>
              {counts.newCount} new · {counts.changedCount} changed · {counts.skipCount} already set
            </p>
          </div>
          <StatePill variant={action.applicable ? "update" : "ok"} label={action.applied_state} />
        </header>
        <ul className="codex__scaffold-items">
          {action.preview_items.map((item) => (
            <li key={item.key}>
              <label className="codex__scaffold-item">
                <input
                  type="checkbox"
                  checked={selectedKeys.has(item.key)}
                  disabled={item.state === "skip"}
                  onChange={(event) => onToggle(item.key, event.currentTarget.checked)}
                />
                <span className="codex__scaffold-item-path">{item.rel_path}</span>
                <StatePill
                  variant={
                    item.state === "changed" ? "update" : item.state === "new" ? "open" : "ok"
                  }
                  label={item.state}
                />
              </label>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="codex__scaffold-apply-btn"
          onClick={onApply}
          disabled={selectedKeys.size === 0}
        >
          Review {selectedKeys.size}
        </button>
      </div>
    </article>
  );
}

function countConversions(
  rows: Array<{
    state: ConversionState;
  }>,
) {
  const byState: Record<ConversionState, number> = {
    converted: 0,
    "not-converted": 0,
    "codex-only": 0,
    stale: 0,
    unsupported: 0,
  };
  for (const row of rows) byState[row.state] += 1;
  return {
    byState,
    converted: byState.converted,
    attention: rows.length - byState.converted - byState["codex-only"],
  };
}

function selectedKeysFor(action: LocalConfigAction, selection: SelectionState): Set<string> {
  const override = selection[action.key];
  if (override !== undefined) return override;
  return new Set(action.preview_items.filter((item) => item.selected).map((item) => item.key));
}

function updateSelection(
  current: SelectionState,
  action: LocalConfigAction,
  itemKey: string,
  checked: boolean,
): SelectionState {
  const next = { ...current };
  const selected = new Set(selectedKeysFor(action, current));
  if (checked) selected.add(itemKey);
  else selected.delete(itemKey);
  next[action.key] = selected;
  return next;
}

function countPreviewItems(action: LocalConfigAction) {
  return {
    newCount: action.preview_items.filter((item) => item.state === "new").length,
    changedCount: action.preview_items.filter((item) => item.state === "changed").length,
    skipCount: action.preview_items.filter((item) => item.state === "skip").length,
  };
}

function conversionVariant(
  state: "converted" | "not-converted" | "codex-only" | "stale" | "unsupported",
) {
  if (state === "converted") return "ok";
  if (state === "stale") return "stale";
  if (state === "unsupported") return "unavailable";
  return "update";
}

function conversionDecisionCopy(state: ConversionState) {
  switch (state) {
    case "converted":
      return "Source and generated output are aligned.";
    case "codex-only":
      return "Native Codex asset; no Claude source is expected.";
    case "not-converted":
      return "Source exists but no Codex output has been emitted.";
    case "stale":
      return "Generated output no longer matches its source.";
    case "unsupported":
      return "This asset kind cannot be translated automatically.";
  }
}
