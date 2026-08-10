// Pure helpers for the Environment module: sensitive-name detection, state-pill variant mapping
// for curated/system rows, and the enabled/total summary count — kept out of the component tree.
import type { EnvEntry } from "@/api/securityEnvironment";
import type { StatePillVariant } from "@/components/StatePill";

export function isSensitiveEnvironmentEntry(entry: EnvEntry): boolean {
  return /(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|CREDENTIAL|AUTH|COOKIE|SESSION)/i.test(
    entry.name,
  );
}

export function sourceVariant(source: string): StatePillVariant {
  switch (source) {
    case "system":
      return "ok";
    case "default":
      return "degraded";
    case "unset":
      return "missing";
    default:
      return "unavailable";
  }
}

export function systemEntryVariant(entry: EnvEntry): StatePillVariant {
  if (isSensitiveEnvironmentEntry(entry)) return "degraded";
  if (entry.is_path) return "ok";
  return "unavailable";
}

export function systemEntryLabel(entry: EnvEntry): string {
  if (isSensitiveEnvironmentEntry(entry)) return "redacted";
  if (entry.is_path) return "path";
  return "value";
}

export function countActive(entries: EnvEntry[], getValue: (entry: EnvEntry) => string): number {
  return entries.filter((entry) => getValue(entry).trim() !== "").length;
}
