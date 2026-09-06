// Names and metadata for one source's entries. There is no value column: values arrive only
// through the per-row eye in RevealCell, one at a time (FR-008/12). Entries are grouped by
// container so a source with several deployment targets or launch profiles reads as the
// several groups it is (FR-009, US5).
import type { VariableContainer, VariableEntry } from "@/api/envSources";
import type { RevealState } from "@/modules/environment/components/RevealCell";
import { RevealCell } from "@/modules/environment/components/RevealCell";

export interface EnvSourceTableProps {
  containers: VariableContainer[];
  revealed: Record<string, RevealState>;
  pendingKey: string | null;
  onReveal: (entry: VariableEntry) => void;
  onMask: (entry: VariableEntry) => void;
}

export function entryKey(entry: VariableEntry): string {
  return `${entry.source_id}|${entry.container_id}|${entry.name}`;
}

export function EnvSourceTable({
  containers,
  revealed,
  pendingKey,
  onReveal,
  onMask,
}: EnvSourceTableProps) {
  const grouped = containers.filter((container) => container.entries.length > 0);
  const showGroupHeadings = grouped.length > 1;

  return (
    <div className="env-sources__table">
      {grouped.map((container) => (
        <section key={container.id} className="env-sources__group">
          {showGroupHeadings ? (
            <h3 className="env-sources__group-heading">
              {container.label}
              {container.qualifier !== null ? (
                <span className="env-sources__group-qualifier">{container.qualifier}</span>
              ) : null}
            </h3>
          ) : null}
          <table className="env-sources__grid" aria-label={`Variables in ${container.label}`}>
            <thead>
              <tr>
                <th scope="col">Variable</th>
                <th scope="col">Where it comes from</th>
                <th scope="col">Last changed</th>
                <th scope="col">Value</th>
              </tr>
            </thead>
            <tbody>
              {container.entries.map((entry) => (
                <tr key={entryKey(entry)}>
                  <th scope="row">
                    <code className="env-sources__name">{entry.name}</code>
                    {entry.description !== "" ? (
                      <span className="env-sources__description">{entry.description}</span>
                    ) : null}
                  </th>
                  <td>
                    <Attribution container={container} entry={entry} />
                  </td>
                  <td>
                    <span className="env-sources__updated">{entry.updated_at ?? "—"}</span>
                  </td>
                  <td>
                    <RevealCell
                      name={entry.name}
                      retrievability={entry.retrievability}
                      retrievabilityReason={entry.retrievability_reason}
                      revealed={revealed[entryKey(entry)] ?? null}
                      isPending={pendingKey === entryKey(entry)}
                      onReveal={() => onReveal(entry)}
                      onMask={() => onMask(entry)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}

function Attribution({ container, entry }: { container: VariableContainer; entry: VariableEntry }) {
  return (
    <span className="env-sources__attribution">
      {entry.target !== null ? (
        <span className="env-sources__badge" data-badge="target">
          {entry.target}
        </span>
      ) : null}
      {entry.entry_type !== null ? (
        <span className="env-sources__badge" data-badge="type">
          {entry.entry_type}
        </span>
      ) : null}
      {container.layer !== null ? (
        <span
          className="env-sources__layer"
          data-wins={container.layer.wins ? "true" : "false"}
          title={
            container.layer.wins
              ? `${container.layer.name} takes effect over the other layers found here`
              : `${container.layer.name} is overridden by a higher-precedence layer found here`
          }
        >
          {container.layer.name}
          <span className="env-sources__layer-verdict">
            {container.layer.wins ? "wins" : "overridden"}
          </span>
        </span>
      ) : null}
    </span>
  );
}
