// Global connectivity/health strip: backend version + per-module health summary; auto-recovers
// because TanStack Query keeps polling GET /api/health regardless of the last outcome.
import { useHealth } from "@/api/health";
import { StatePill } from "@/components/StatePill";

export function HealthStrip() {
  const health = useHealth();

  if (health.isPending) {
    return (
      <div className="health-strip health-strip--connecting select-none" role="status">
        <StatePill variant="loading" />
        <span>Connecting to backend…</span>
      </div>
    );
  }

  if (health.isError) {
    return (
      <div className="health-strip health-strip--reconnecting select-none" role="alert">
        <StatePill variant="failed" />
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

  return (
    <div className="health-strip health-strip--ok select-none" role="status">
      <StatePill
        variant={attentionModules.length === 0 ? "ok" : hasFailure ? "failed" : "degraded"}
      />
      <span className="health-strip__version">Cabal v{health.data.version}</span>
      {attentionModules.length > 0 ? (
        <span className="health-strip__degraded" title={attentionTitle}>
          {attentionModules.length} {attentionModules.length === 1 ? "module" : "modules"} need
          attention
        </span>
      ) : null}
    </div>
  );
}
