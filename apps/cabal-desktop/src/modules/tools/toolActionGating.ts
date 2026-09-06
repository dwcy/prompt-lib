// Derives which install/update action (if any) a tool's current status permits.
import type { ToolStatusState } from "@/api/tools";

export type ToolActionKind = "tools.install" | "tools.update" | null;

// missing/error -> nothing usable is installed (error retries the probe via a fresh install attempt).
// update_available -> a newer version exists, offer Update. installed/unsupported/manual_required
// never show an action: installed has nothing to do, and unsupported/manual_required are explicitly
// excluded per spec (no automation path exists for either).
export function toolActionForState(state: ToolStatusState): ToolActionKind {
  if (state === "missing" || state === "error") return "tools.install";
  if (state === "update_available") return "tools.update";
  return null;
}
