import type { DriftFlags, ModuleState } from "@/api/schemas";
import type { ModuleKey } from "@/modules/registry";

export interface NavBadgesProps {
  moduleKey: ModuleKey;
  driftFlags: DriftFlags | null;
  healthState: ModuleState | null;
  healthDetail: string | null;
}

export function NavBadges({ moduleKey, driftFlags, healthState, healthDetail }: NavBadgesProps) {
  const showClaudeDrift = moduleKey === "config_deploy" && driftFlags?.claude === true;
  const showCodexDrift = moduleKey === "codex" && driftFlags?.codex === true;
  const showHealth = healthState !== null && healthState !== "ok";
  if (!showClaudeDrift && !showCodexDrift && !showHealth) return null;

  return (
    <>
      {showClaudeDrift || showCodexDrift ? <span className="sidebar-nav__badge">Drift</span> : null}
      {showHealth ? (
        <span
          className={`sidebar-nav__badge sidebar-nav__badge--${healthState}`}
          title={healthDetail || healthState}
        >
          {healthState}
        </span>
      ) : null}
    </>
  );
}
