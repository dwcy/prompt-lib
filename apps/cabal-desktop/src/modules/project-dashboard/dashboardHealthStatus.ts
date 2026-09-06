// Maps a section's raw AvailabilityState (+ enrich_state override) to the gauge/pill visuals used
// by ProjectHealthCard — the backend enum has no built-in "severity", so this is where that
// judgement call lives, kept out of the presentational component. The gauge center is icon-only;
// the state's text description already lives in the StatePill next to it (ProjectHealthCard passes
// effectiveState as its label), so the gauge doesn't repeat it as a caption.
import type { GaugeTone } from "@/components/Gauge";
import type { StatePillVariant } from "@/components/StatePill";

const WARNING_STATES = new Set([
  "no_cli",
  "not_linked",
  "not_authed",
  "token_missing",
  "token_rejected",
]);

const ICON_HEALTHY = "💚";
const ICON_TIMEOUT = "⏳";
const ICON_ERROR = "🔔";
const ICON_WARNING = "⚠️";

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
      gaugeValue: ICON_HEALTHY,
      gaugeCaption: "",
      pillVariant: "ok",
    };
  }

  if (effectiveState === "timeout") {
    return {
      effectiveState,
      tone: "danger",
      gaugeFraction: 0.15,
      gaugeValue: ICON_TIMEOUT,
      gaugeCaption: "",
      pillVariant: "failed",
    };
  }

  if (effectiveState === "error") {
    return {
      effectiveState,
      tone: "danger",
      gaugeFraction: 0.15,
      gaugeValue: ICON_ERROR,
      gaugeCaption: "",
      pillVariant: "failed",
    };
  }

  const isKnownWarning = WARNING_STATES.has(effectiveState);
  return {
    effectiveState,
    tone: "warning",
    gaugeFraction: isKnownWarning ? 0.45 : 0.3,
    gaugeValue: ICON_WARNING,
    gaugeCaption: "",
    pillVariant: "degraded",
  };
}
