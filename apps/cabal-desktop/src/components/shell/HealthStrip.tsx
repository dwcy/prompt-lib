// Global connectivity/health strip (console redesign): pulsing live dot + backend state text,
// clickable to open the per-module breakdown; auto-recovers because TanStack Query keeps polling
// GET /api/health regardless of the last outcome.
import { useState } from "react";
import { useHealth } from "@/api/health";
import { HealthModulesDialog } from "@/components/shell/HealthModulesDialog";

export function HealthStrip() {
  const health = useHealth();
  const [isDialogOpen, setIsDialogOpen] = useState(false);

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
        <span>disconnected</span>
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
  const tone = attentionModules.length === 0 ? "ok" : hasFailure ? "failed" : "degraded";
  const label = attentionModules.length === 0 ? "backend connected" : "backend degraded";

  return (
    <>
      <button
        type="button"
        className="health-strip health-strip--ok health-strip__trigger select-none"
        onClick={() => setIsDialogOpen(true)}
        aria-haspopup="dialog"
        title="Show module health"
      >
        <span className={`health-strip__dot health-strip__dot--${tone}`} aria-hidden="true" />
        <span className={`health-strip__label health-strip__label--${tone}`}>{label}</span>
        {attentionModules.length > 0 ? (
          <span className="health-strip__degraded">
            {attentionModules.length} {attentionModules.length === 1 ? "module" : "modules"} need
            attention
          </span>
        ) : null}
      </button>

      {isDialogOpen ? (
        <HealthModulesDialog modules={health.data.modules} onClose={() => setIsDialogOpen(false)} />
      ) : null}
    </>
  );
}
