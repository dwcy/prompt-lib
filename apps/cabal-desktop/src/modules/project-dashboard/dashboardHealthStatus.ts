// Maps a section's raw AvailabilityState (+ enrich_state override) to the gauge/pill visuals used
// by ProjectHealthCard — the backend enum has no built-in "severity", so this is where that
// judgement call lives, kept out of the presentational component.
import type { GaugeTone } from "@/components/Gauge";
import type { StatePillVariant } from "@/components/StatePill";

const WARNING_STATES = new Set([
  "no_cli",
  "not_linked",
  "not_authed",
  "token_missing",
  "token_rejected",
]);
const DANGER_STATES = new Set(["timeout", "error"]);

const CAPTION_BY_STATE: Record<string, string> = {
  ok: "healthy",
  no_cli: "no CLI",
  not_linked: "not linked",
  not_authed: "not authed",
  token_missing: "no token",
  token_rejected: "bad token",
  timeout: "timeout",
  error: "error",
};

export interface HealthStatus {
  /** Raw state string shown verbatim on the StatePill, e.g. "token_missing". */
  effectiveState: string;
  tone: GaugeTone;
  gaugeFraction: number;
  gaugeValue: string;
  gaugeCaption: string;
  pillVariant: StatePillVariant;
}

// `enrichState` (Supabase/Vercel token-gated enrichment) wins when it reports a problem the
// top-level `state` doesn't — e.g. a linked project (state: "ok") whose token is missing.
export function resolveHealthStatus(
  state: string | null,
  enrichState: string | null,
): HealthStatus {
  const effectiveState =
    enrichState !== null && enrichState !== "ok" ? enrichState : (state ?? "error");

  if (effectiveState === "ok") {
    return {
      effectiveState,
      tone: "ok",
      gaugeFraction: 1,
      gaugeValue: "OK",
      gaugeCaption: CAPTION_BY_STATE.ok,
      pillVariant: "ok",
    };
  }

  if (DANGER_STATES.has(effectiveState)) {
    return {
      effectiveState,
      tone: "danger",
      gaugeFraction: 0.15,
      gaugeValue: "ERR",
      gaugeCaption: CAPTION_BY_STATE[effectiveState] ?? effectiveState,
      pillVariant: "failed",
    };
  }

  const isKnownWarning = WARNING_STATES.has(effectiveState);
  return {
    effectiveState,
    tone: "warning",
    gaugeFraction: isKnownWarning ? 0.45 : 0.3,
    gaugeValue: "WARN",
    gaugeCaption: CAPTION_BY_STATE[effectiveState] ?? effectiveState,
    pillVariant: "degraded",
  };
}
