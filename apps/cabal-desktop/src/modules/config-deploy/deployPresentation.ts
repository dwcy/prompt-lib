// Shared wording/badge mapping for the deploy views, so the tree, the diff header and the file
// viewer never disagree about what "changed" or "new" looks like.
import type { ConfigFileState } from "@/api/config";
import type { StatePillVariant } from "@/components/StatePill";

export function fileStateVariant(state: ConfigFileState): StatePillVariant {
  if (state === "changed") return "update";
  return state === "new" ? "open" : "ok";
}
