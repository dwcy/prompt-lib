// Presentation helpers shared by the Tools table and detail pane — ToolStatus.state → StatePill
// variant mapping plus channel/timestamp display formatting — so the two surfaces never drift.
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

export function formatInstallChannel(value: string): string {
  return value.replaceAll("_", " ");
}

export function formatCheckedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unavailable";
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}
