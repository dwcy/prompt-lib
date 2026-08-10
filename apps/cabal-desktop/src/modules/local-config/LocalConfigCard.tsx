// Single blueprint/group action card: header + applied-state pill, per-item preview toggle list,
// and the confirmed-apply trigger button. Rendered once per LocalConfigAction in the module list.
import type { LocalConfigAction } from "@/api/config";
import { StatePill } from "@/components/StatePill";
import { LocalConfigToggle } from "@/modules/local-config/LocalConfigToggle";

export function LocalConfigCard({
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
    <article className="lcfg__card">
      <span className="lcfg__card-number">{String(step).padStart(2, "0")}</span>
      <div className="lcfg__card-body">
        <header className="lcfg__card-header">
          <div>
            <h2>{action.label}</h2>
            <p>
              {counts.newCount} new · {counts.changedCount} changed · {counts.skipCount} already set
            </p>
          </div>
          <StatePill variant={action.applicable ? "update" : "ok"} label={action.applied_state} />
        </header>
        <ul className="lcfg__items">
          {action.preview_items.map((item) => {
            const checked = selectedKeys.has(item.key);
            return (
              <li key={item.key} className="lcfg__item">
                <LocalConfigToggle
                  checked={checked}
                  disabled={item.state === "skip"}
                  label={`Include ${item.rel_path}`}
                  onToggle={() => onToggle(item.key, !checked)}
                />
                <span className="lcfg__item-path">{item.rel_path}</span>
                <StatePill
                  variant={
                    item.state === "changed" ? "update" : item.state === "new" ? "open" : "ok"
                  }
                  label={item.state}
                />
              </li>
            );
          })}
        </ul>
        <button
          type="button"
          className="lcfg__apply-btn"
          onClick={onApply}
          disabled={selectedKeys.size === 0}
        >
          Review {selectedKeys.size}
        </button>
      </div>
    </article>
  );
}

export function BlueprintMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "new" | "changed" | "stable";
}) {
  return (
    <span className={`lcfg__metric lcfg__metric--${tone}`}>
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

function countPreviewItems(action: LocalConfigAction) {
  return {
    newCount: action.preview_items.filter((item) => item.state === "new").length,
    changedCount: action.preview_items.filter((item) => item.state === "changed").length,
    skipCount: action.preview_items.filter((item) => item.state === "skip").length,
  };
}
