import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { type ModelAssignment, useModels } from "@/api/observability";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import "./ModelAssignmentsModule.css";

export function ModelAssignmentsModule() {
  const modelsQuery = useModels();
  const [kindFilter, setKindFilter] = useState<"all" | "agent" | "skill">("all");
  const [search, setSearch] = useState("");
  const [attentionOnly, setAttentionOnly] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const assignAction = useAction("models.assign");
  const queryClient = useQueryClient();

  useEffect(() => {
    if (assignAction.phase !== "succeeded") return;
    queryClient.invalidateQueries({ queryKey: ["cabal", "global", "models"] });
    if (pendingKey !== null) {
      setDrafts((current) => {
        const next = { ...current };
        delete next[pendingKey];
        return next;
      });
      setPendingKey(null);
    }
    assignAction.reset();
  }, [assignAction, pendingKey, queryClient]);

  const rows = useMemo(() => {
    const items = modelsQuery.data?.assignments ?? [];
    const normalizedSearch = search.trim().toLowerCase();
    return items.filter((item) => {
      if (kindFilter !== "all" && item.asset_kind !== kindFilter) return false;
      if (attentionOnly && item.valid && item.repo_and_target_in_sync) return false;
      if (normalizedSearch === "") return true;
      return `${item.asset_name} ${item.pinned_model} ${item.resolved_to ?? ""}`
        .toLowerCase()
        .includes(normalizedSearch);
    });
  }, [attentionOnly, modelsQuery.data, kindFilter, search]);

  if (modelsQuery.isPending) {
    return <EmptyState title="Loading model assignments…" />;
  }

  if (modelsQuery.isError) {
    return <EmptyState title="Could not load model assignments" body={modelsQuery.error.message} />;
  }

  const payload = modelsQuery.data;
  const stagedCount = payload.assignments.filter((assignment) => {
    const draft = drafts[assignmentKey(assignment)];
    return draft !== undefined && draft !== assignment.pinned_model;
  }).length;
  const lanes = (["agent", "skill"] as const)
    .map((kind) => ({ kind, rows: rows.filter((row) => row.asset_kind === kind) }))
    .filter((lane) => kindFilter === "all" || lane.kind === kindFilter);

  return (
    <div className="ma-module">
      <section className="ma-header">
        <div className="ma-header__intro">
          <span className="ma-eyebrow">Routing matrix</span>
          <h1>Agent and skill model pins</h1>
          <p>
            Alias pins are compared against the deployed target so stale assignments are visible
            before they surprise a session.
          </p>
        </div>
        <div className="ma-header__metrics">
          <span className="ma-header__metric">
            <strong>{payload.counts.total}</strong>
            <small>assets</small>
          </span>
          <span className="ma-header__metric">
            <strong>{payload.counts.out_of_sync}</strong>
            <small>out of sync</small>
          </span>
          <span className="ma-header__metric">
            <strong>{payload.counts.invalid}</strong>
            <small>invalid</small>
          </span>
        </div>
      </section>

      <section className="ma-overview">
        <div className="ma-overview__intro">
          <span className="ma-eyebrow">Repository to runtime</span>
          <strong>{stagedCount} route change(s) staged</strong>
          <p>Every pin is traced through alias resolution to the deployed target.</p>
        </div>
        <ModelDistribution assignments={payload.assignments} />
      </section>

      <div className="ma-controls">
        <fieldset className="ma-segmented">
          <legend className="ma-vh">Filter model assignments</legend>
          {(["all", "agent", "skill"] as const).map((kind) => (
            <button
              key={kind}
              type="button"
              className={kindFilter === kind ? "is-active" : undefined}
              aria-pressed={kindFilter === kind}
              onClick={() => setKindFilter(kind)}
            >
              {kind}
            </button>
          ))}
        </fieldset>
        <label className="ma-search">
          <span className="ma-vh">Search model routes</span>
          <input
            type="search"
            value={search}
            placeholder="Search routes"
            onChange={(event) => setSearch(event.currentTarget.value)}
          />
        </label>
        <label className="ma-attention">
          <input
            type="checkbox"
            checked={attentionOnly}
            onChange={(event) => setAttentionOnly(event.currentTarget.checked)}
          />
          <span>Attention only</span>
        </label>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No model routes match this view" />
      ) : (
        <div className="ma-lanes">
          {lanes.map((lane) => (
            <section key={lane.kind} className="ma-lane">
              <header className="ma-lane__header">
                <div>
                  <span className="ma-eyebrow">{lane.kind} fleet</span>
                  <h2>{lane.kind === "agent" ? "Agent routes" : "Skill routes"}</h2>
                </div>
                <span className="ma-lane__count">{lane.rows.length}</span>
              </header>
              <div className="ma-grid">
                {lane.rows.map((assignment) => {
                  const key = assignmentKey(assignment);
                  const draft = drafts[key] ?? assignment.pinned_model;
                  return (
                    <ModelRouteCard
                      key={key}
                      assignment={assignment}
                      draft={draft}
                      onDraft={(model) => setDrafts((current) => ({ ...current, [key]: model }))}
                      onStage={() => {
                        setPendingKey(key);
                        assignAction.prepare({
                          asset_kind: assignment.asset_kind,
                          asset_name: assignment.asset_name,
                          model: draft,
                        });
                      }}
                    />
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}

      <ConfirmDialog
        isOpen={assignAction.phase !== "idle" && assignAction.phase !== "succeeded"}
        actionTitle="Assign Model Pin"
        ticket={assignAction.ticket}
        phase={assignAction.phase}
        reviewNotice={assignAction.reviewNotice}
        error={assignAction.error}
        onConfirm={assignAction.confirm}
        onCancel={assignAction.reset}
      />
    </div>
  );
}

function ModelRouteCard({
  assignment,
  draft,
  onDraft,
  onStage,
}: {
  assignment: ModelAssignment;
  draft: string;
  onDraft: (model: string) => void;
  onStage: () => void;
}) {
  const staged = draft !== assignment.pinned_model;
  return (
    <article className={`ma-card${staged ? " is-staged" : ""}`}>
      <header className="ma-card__header">
        <span>
          <strong>{assignment.asset_name}</strong>
          <small>{assignment.asset_kind}</small>
        </span>
        <StatePill
          variant={
            !assignment.valid ? "error" : assignment.repo_and_target_in_sync ? "ok" : "degraded"
          }
          label={
            !assignment.valid ? "invalid" : assignment.repo_and_target_in_sync ? "synced" : "drift"
          }
        />
      </header>
      <div className="ma-route" data-drift={!assignment.repo_and_target_in_sync}>
        <span className="ma-route__step">
          <small>repository pin</small>
          <strong>{assignment.pinned_model}</strong>
        </span>
        <i className="ma-route__arrow" aria-hidden="true">
          →
        </i>
        <span className="ma-route__step">
          <small>resolves to</small>
          <strong>{assignment.resolved_to ?? assignment.pinned_model}</strong>
        </span>
        <i className="ma-route__arrow" aria-hidden="true">
          →
        </i>
        <span className="ma-route__step">
          <small>deployed target</small>
          <strong>{assignment.target_model ?? "not reported"}</strong>
        </span>
      </div>
      <div className="ma-card__command">
        <label className="ma-card__picker">
          <span>Next repository pin</span>
          <select value={draft} onChange={(event) => onDraft(event.currentTarget.value)}>
            {assignment.assignable_models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="ma-card__stage-btn" disabled={!staged} onClick={onStage}>
          Review route change
        </button>
      </div>
    </article>
  );
}

function ModelDistribution({ assignments }: { assignments: ModelAssignment[] }) {
  const counts = new Map<string, number>();
  for (const assignment of assignments) {
    counts.set(assignment.pinned_model, (counts.get(assignment.pinned_model) ?? 0) + 1);
  }
  const rows = Array.from(counts.entries()).sort((left, right) => right[1] - left[1]);
  const total = Math.max(assignments.length, 1);
  return (
    <section className="ma-distribution" aria-label="Model pin distribution">
      {rows.map(([model, count]) => (
        <div key={model} className="ma-distribution__row">
          <span>
            <strong>{model}</strong>
            <small>{count}</small>
          </span>
          <i className="ma-distribution__track">
            <span
              className="ma-distribution__fill"
              style={{ width: `${(count / total) * 100}%` }}
            />
          </i>
        </div>
      ))}
    </section>
  );
}

function assignmentKey(assignment: ModelAssignment) {
  return `${assignment.asset_kind}:${assignment.asset_name}`;
}
