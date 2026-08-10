// Pure selection-state helpers shared between LocalConfigModule and LocalConfigCard: tracks
// per-group item-key overrides so unedited groups fall back to the server-provided defaults.
import type { LocalConfigAction } from "@/api/config";

export type SelectionState = Record<string, Set<string>>;

export function selectedKeysFor(action: LocalConfigAction, selection: SelectionState): Set<string> {
  const override = selection[action.key];
  if (override !== undefined) return override;
  return new Set(action.preview_items.filter((item) => item.selected).map((item) => item.key));
}

export function updateSelection(
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

export function summarizePlan(actions: LocalConfigAction[], selection: SelectionState) {
  const previews = actions.flatMap((item) => item.preview_items);
  return {
    selected: actions.reduce((total, item) => total + selectedKeysFor(item, selection).size, 0),
    ready: actions.filter((item) => item.applicable).length,
    complete: actions.filter((item) => !item.applicable).length,
    newCount: previews.filter((item) => item.state === "new").length,
    changedCount: previews.filter((item) => item.state === "changed").length,
    skipCount: previews.filter((item) => item.state === "skip").length,
  };
}
