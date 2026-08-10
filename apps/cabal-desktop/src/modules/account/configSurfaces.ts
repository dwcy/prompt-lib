// Groups Claude-info config documents into Global (~/.claude) vs Local (project) scopes for the
// Configuration surfaces tab switcher — grouped by the real document labels the API returns.
import type { ClaudeInfoPayload } from "@/api/observability";

export type ConfigDocument = ClaudeInfoPayload["documents"][number];
export type ConfigScope = "global" | "local";

const GLOBAL_LABELS = new Set(["Repo global instructions", "Deployed global instructions"]);
const LOCAL_LABELS = new Set(["Repo project instructions", "Selected project instructions"]);

export function groupDocumentsByScope(
  documents: ConfigDocument[],
): Record<ConfigScope, ConfigDocument[]> {
  return {
    global: documents.filter((doc) => GLOBAL_LABELS.has(doc.label)),
    local: documents.filter((doc) => LOCAL_LABELS.has(doc.label)),
  };
}
