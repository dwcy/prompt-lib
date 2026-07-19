// Global connectivity/health strip (console redesign): pulsing live dot + collector state text +
// backend version; auto-recovers because TanStack Query keeps polling GET /api/health regardless
// of the last outcome.
import { useHealth } from "@/api/health";

export function HealthStrip() {
  const health = useHealth();

  if (health.isPending) {
    return (
      <div className="health-strip health-strip--connecting select-none" role="status">
        <span className="health-strip__dot health-strip__dot--connecting" aria-hidden="true" />
        <span>Connecting to backend…</span>
      </div>
    );
  }

  if (health.isError) {
    return (
      <div className="health-strip health-strip--reconnecting select-none" role="alert">
        <span className="health-strip__dot health-strip__dot--failed" aria-hidden="true" />
        <span>Backend unavailable. Reconnecting…</span>
      </div>
    );
  }

  const attentionModules = health.data.modules.filter(
    (module) =>
      module.state === "degraded" || module.state === "failed" || module.state === "unavailable",
  );
  const hasFailure = attentionModules.some(
    (module) => module.state === "failed" || module.state === "unavailable",
  );
  const attentionTitle = attentionModules
    .map((module) => `${module.module}: ${module.state}`)
    .join("\n");
  const tone = attentionModules.length === 0 ? "ok" : hasFailure ? "failed" : "degraded";

  return (
    <div className="health-strip health-strip--ok select-none" role="status">
      <span className={`health-strip__dot health-strip__dot--${tone}`} aria-hidden="true" />
      <span className={`health-strip__label health-strip__label--${tone}`}>
        {attentionModules.length === 0 ? "collectors responsive" : "collectors degraded"}
      </span>
      <span className="health-strip__version">v{health.data.version}</span>
      {attentionModules.length > 0 ? (
        <span className="health-strip__degraded" title={attentionTitle}>
          {attentionModules.length} {attentionModules.length === 1 ? "module" : "modules"} need
          attention
        </span>
      ) : null}
    </div>
  );
}
