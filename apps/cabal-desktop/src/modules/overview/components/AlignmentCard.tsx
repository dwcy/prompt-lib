// Deployment-alignment card: Claude and Codex source-to-runtime drift tiles with the three-bar
// track viz, drift StatePill, and deep links into Config Deploy / Codex Parity.
import type { DriftFlags } from "@/api/schemas";
import { StatePill } from "@/components/StatePill";
import type { ModuleKey } from "@/modules/registry";

interface AlignmentLane {
  key: string;
  name: string;
  detail: string;
  module: ModuleKey;
}

const ALIGNMENT_LANES: AlignmentLane[] = [
  {
    key: "claude",
    name: "Claude",
    detail: "Global instructions, skills, agents, and hooks",
    module: "config_deploy",
  },
  {
    key: "codex",
    name: "Codex",
    detail: "Converted skills, templates, and local assets",
    module: "codex",
  },
];

export interface AlignmentCardProps {
  driftFlags: DriftFlags;
  onOpen: (module: ModuleKey) => void;
}

export function AlignmentCard({ driftFlags, onOpen }: AlignmentCardProps) {
  const driftCount = Number(driftFlags.claude) + Number(driftFlags.codex);
  return (
    <section className="overview-card overview-alignment" aria-label="Deployment alignment">
      <header className="overview-card__header">
        <b>Deployment alignment</b>
        <span>{driftCount === 0 ? "aligned" : `${driftCount} changed`}</span>
      </header>
      <div className="overview-alignment__tiles">
        {ALIGNMENT_LANES.map((lane) => {
          const hasDrift = driftFlags[lane.key === "claude" ? "claude" : "codex"];
          return (
            <button
              key={lane.key}
              type="button"
              className="overview-alignment-tile select-none"
              onClick={() => onOpen(lane.module)}
              aria-label={`Review ${lane.name} deployment`}
            >
              <span className="overview-alignment-tile__head">
                <b>{lane.name}</b>
                <StatePill
                  variant={hasDrift ? "degraded" : "ok"}
                  label={hasDrift ? "drift" : "in sync"}
                />
              </span>
              <small>{lane.detail}</small>
              <span className="overview-alignment-tile__track" data-drift={hasDrift} aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
            </button>
          );
        })}
      </div>
      <p className="overview-alignment__note">
        Source to runtime — drift means repo changes are waiting for a deploy or conversion check.
      </p>
    </section>
  );
}
