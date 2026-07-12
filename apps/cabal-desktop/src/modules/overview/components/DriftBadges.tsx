// Config drift indicators (claude/codex) surfaced from Overview.drift_flags (FR-011/data-model.md).
import type { DriftFlags } from "@/api/schemas";
import { StatePill } from "@/components/StatePill";

export interface DriftBadgesProps {
  driftFlags: DriftFlags;
}

export function DriftBadges({ driftFlags }: DriftBadgesProps) {
  return (
    <div className="overview-drift-badges select-none" role="status">
      <span className="overview-drift-badges__item">
        Claude config
        <StatePill
          variant={driftFlags.claude ? "degraded" : "ok"}
          label={driftFlags.claude ? "drift" : "in sync"}
        />
      </span>
      <span className="overview-drift-badges__item">
        Codex config
        <StatePill
          variant={driftFlags.codex ? "degraded" : "ok"}
          label={driftFlags.codex ? "drift" : "in sync"}
        />
      </span>
    </div>
  );
}
