import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { type ScheduledTask, useScheduledTasks } from "@/api/scheduledTasks";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import "./ScheduledTasksModule.css";

type TaskFilter = "all" | "active" | "paused" | "completed";

export function ScheduledTasksModule() {
  const tasksQuery = useScheduledTasks();
  const deleteAction = useAction("scheduled_tasks.delete");
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (deleteAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: ["cabal", "global", "scheduled-tasks"] });
    setSelectedId(null);
    deleteAction.reset();
  }, [deleteAction, queryClient]);

  const visibleTasks = useMemo(() => {
    const tasks = tasksQuery.data?.items ?? [];
    return filter === "all" ? tasks : tasks.filter((task) => task.status === filter);
  }, [filter, tasksQuery.data]);

  const selected = useMemo(
    () => visibleTasks.find((task) => task.id === selectedId) ?? visibleTasks[0] ?? null,
    [selectedId, visibleTasks],
  );

  useEffect(() => {
    if (selected !== null && selected.id !== selectedId) setSelectedId(selected.id);
  }, [selected, selectedId]);

  if (tasksQuery.isPending) return <EmptyState title="Loading scheduled tasks…" />;
  if (tasksQuery.isError) {
    return <EmptyState title="Could not load scheduled tasks" body={tasksQuery.error.message} />;
  }

  const data = tasksQuery.data;
  const filters: TaskFilter[] = ["all", "active", "paused", "completed"];

  return (
    <div className="scheduled-tasks">
      <header className="scheduled-tasks__header">
        <div>
          <span className="scheduled-tasks__eyebrow">Local automation control</span>
          <h1>Claude + Codex schedules</h1>
          <p>Review locally runnable tasks and remove definitions with a guarded confirmation.</p>
        </div>
        <button
          type="button"
          onClick={() => void tasksQuery.refetch()}
          disabled={tasksQuery.isFetching}
        >
          {tasksQuery.isFetching ? "Refreshing…" : "Refresh tasks"}
        </button>
      </header>

      <section className="scheduled-tasks__providers" aria-label="Scheduler sources">
        {data.providers.map((provider) => (
          <article key={provider.provider} className="scheduled-tasks__provider">
            <div className="scheduled-tasks__provider-title">
              <span
                className={`scheduled-tasks__provider-mark is-${provider.provider}`}
                aria-hidden="true"
              >
                {provider.provider === "claude" ? "C" : "⌘"}
              </span>
              <div>
                <strong>{provider.label}</strong>
                <small>{provider.source}</small>
              </div>
              <span className="scheduled-tasks__provider-count">{provider.task_count}</span>
            </div>
            <p>{provider.detail}</p>
            <div className="scheduled-tasks__provider-footer">
              <StatePill
                variant={provider.detected ? "ok" : "unavailable"}
                label={provider.detected ? "detected" : "not detected"}
              />
              <a href={provider.management_url} target="_blank" rel="noreferrer">
                {provider.provider === "claude" ? "Cloud routines ↗" : "Scheduled docs ↗"}
              </a>
            </div>
          </article>
        ))}
      </section>

      <section className="scheduled-tasks__workspace">
        <div className="scheduled-tasks__list-panel">
          <header className="scheduled-tasks__list-header">
            <div>
              <span className="scheduled-tasks__eyebrow">Task inventory</span>
              <strong>{data.counts.all} definitions</strong>
            </div>
            <fieldset className="scheduled-tasks__filters" aria-label="Filter tasks">
              {filters.map((value) => (
                <button
                  key={value}
                  type="button"
                  className={filter === value ? "is-active" : undefined}
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                >
                  {value} <span>{data.counts[value]}</span>
                </button>
              ))}
            </fieldset>
          </header>

          {visibleTasks.length === 0 ? (
            <EmptyState
              title={data.items.length === 0 ? "No local scheduled tasks" : `No ${filter} tasks`}
              body={
                data.items.length === 0
                  ? "Create a local task in Claude Desktop or Codex and refresh this view."
                  : "Choose another status filter."
              }
            />
          ) : (
            <div className="scheduled-tasks__table">
              <div className="scheduled-tasks__table-head select-none" aria-hidden="true">
                <span>Task</span>
                <span>Provider</span>
                <span>Schedule</span>
                <span>Status</span>
              </div>
              <ul className="scheduled-tasks__rows" aria-label="Scheduled tasks">
                {visibleTasks.map((task) => (
                  <li key={task.id}>
                    <button
                      type="button"
                      className={`scheduled-tasks__row${selected?.id === task.id ? " is-selected" : ""}`}
                      onClick={() => setSelectedId(task.id)}
                    >
                      <span className="scheduled-tasks__identity">
                        <strong>{task.name}</strong>
                        <small>{task.provider_task_id}</small>
                      </span>
                      <span className="scheduled-tasks__provider-cell">{providerName(task)}</span>
                      <code title={task.schedule}>{task.schedule}</code>
                      <StatePill variant={statusVariant(task.status)} label={task.status} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <aside className="scheduled-tasks__detail" aria-label="Selected scheduled task">
          {selected === null ? (
            <EmptyState title="Select a scheduled task" />
          ) : (
            <TaskDetail
              task={selected}
              onDelete={() =>
                deleteAction.prepare({
                  provider: selected.provider,
                  task_id: selected.provider_task_id,
                })
              }
            />
          )}
        </aside>
      </section>

      <ConfirmDialog action={deleteAction} actionTitle="Delete Scheduled Task" />
    </div>
  );
}

function TaskDetail({ task, onDelete }: { task: ScheduledTask; onDelete: () => void }) {
  return (
    <>
      <header className="scheduled-tasks__detail-header">
        <div>
          <span className="scheduled-tasks__eyebrow">{providerName(task)}</span>
          <h2>{task.name}</h2>
        </div>
        <StatePill variant={statusVariant(task.status)} label={task.status} />
      </header>

      <dl className="scheduled-tasks__facts">
        <div>
          <dt>Schedule</dt>
          <dd>
            <code>{task.schedule}</code>
          </dd>
        </div>
        <div>
          <dt>Next run</dt>
          <dd>{formatTimestamp(task.next_run_at)}</dd>
        </div>
        <div>
          <dt>Workspace</dt>
          <dd title={task.workspace ?? undefined}>{task.workspace ?? "Projectless"}</dd>
        </div>
        <div>
          <dt>Environment</dt>
          <dd>{task.execution_environment ?? "Default"}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{task.model ?? "Default"}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{formatTimestamp(task.updated_at)}</dd>
        </div>
      </dl>

      {task.description ? <p className="scheduled-tasks__description">{task.description}</p> : null}
      <section className="scheduled-tasks__prompt">
        <h3>Run instructions</h3>
        <pre>{task.prompt || "No prompt stored."}</pre>
      </section>

      <footer className="scheduled-tasks__detail-footer">
        <small>
          {task.mirror_count > 1 ? `${task.mirror_count} mirrored task records` : task.source}
        </small>
        <button
          type="button"
          className="scheduled-tasks__delete"
          onClick={onDelete}
          disabled={!task.can_delete}
        >
          Delete task
        </button>
      </footer>
    </>
  );
}

function providerName(task: ScheduledTask): string {
  return task.provider === "claude" ? "Claude" : "Codex";
}

function statusVariant(status: string): StatePillVariant {
  if (status === "active") return "running";
  if (status === "completed") return "succeeded";
  if (status === "paused") return "closed";
  return "unavailable";
}

function formatTimestamp(value: string | null): string {
  if (value === null) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}
