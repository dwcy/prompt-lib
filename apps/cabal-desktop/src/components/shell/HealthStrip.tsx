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
        <span>Reconnecting to backend…</span>
      </div>
    );
  }

  const degradedCount = health.data.modules.filter(
    (module) => module.state === "degraded" || module.state === "failed",
  ).length;

  return (
    <div className="health-strip health-strip--ok select-none" role="status">
      <StatePill variant={degradedCount > 0 ? "degraded" : "ok"} />
      <span className="health-strip__version">cabal v{health.data.version}</span>
      {degradedCount > 0 ? (
        <span className="health-strip__degraded">{degradedCount} module(s) degraded</span>
      ) : null}
    </div>
  );
}
