// Narrow-with-fallback readers for the permissive `Record<string, unknown>` section payloads used
// by Overview/Dashboard (api/schemas.ts's overviewSectionSchema/dashboardSectionSchema) — the
// web-api contract doesn't pin their internal field names, so callers try a list of candidate keys
// and narrow the first typed match, mirroring LogStream's extractLogLine pattern.
export type UnknownSection = Record<string, unknown>;

export function readString(section: UnknownSection, keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = section[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return null;
}

export function readBoolean(section: UnknownSection, keys: readonly string[]): boolean | null {
  for (const key of keys) {
    const value = section[key];
    if (typeof value === "boolean") return value;
  }
  return null;
}

export function readNumber(section: UnknownSection, keys: readonly string[]): number | null {
  for (const key of keys) {
    const value = section[key];
    if (typeof value === "number") return value;
  }
  return null;
}

const UNLINKED_STATE_VALUES = new Set(["not_set_up", "unconfigured", "unlinked", "disabled"]);

// A dashboard section is "hidden-when-unlinked" when it explicitly reports a falsy linked/connected
// flag, or a state value known to mean "not configured yet" — anything else defaults to shown, so a
// section missing this optional metadata never disappears by accident.
export function isSectionLinked(section: UnknownSection): boolean {
  const linkedFlag = readBoolean(section, ["linked", "configured", "connected"]);
  if (linkedFlag === false) return false;
  const state = readString(section, ["state", "status"]);
  if (state !== null && UNLINKED_STATE_VALUES.has(state)) return false;
  return true;
}
