// Maps a ToolStatus.state to the shared StatePill's semantic variant — single source shared by the
// table and the detail drawer so the two never drift apart.
import type { ToolStatusState } from "@/api/tools";
import type { StatePillVariant } from "@/components/StatePill";

export function toStatePillVariant(state: ToolStatusState): StatePillVariant {
  switch (state) {
    case "installed":
      return "installed";
    case "update_available":
      return "update";
    case "missing":
      return "missing";
    case "unsupported":
      return "unavailable";
    case "manual_required":
      return "degraded";
    case "error":
      return "error";
  }
}
