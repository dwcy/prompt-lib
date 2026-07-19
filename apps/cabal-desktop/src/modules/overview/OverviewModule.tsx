// Home Overview: an operator brief, ranked attention queue, deployment alignment, and grouped
// signal ledger with deep links into the corresponding module (T033).
import { useOverview } from "@/api/overview";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import {
  deriveOverviewActions,
  deriveOverviewCards,
  type OverviewCardSummary,
} from "@/modules/overview/overviewSummary";

const SIGNAL_LANES: Array<{
  key: string;
  title: string;
  description: string;
  cardKeys: string[];
}> = [
  {
    key: "operational-core",
    title: "Operational core",
    description: "Project connectivity, recent work, and the active runtime identity.",
    cardKeys: ["dashboard_summary", "recent_sessions", "account"],
  },
  {
    key: "safeguards",
    title: "Safeguards",
    description: "Configuration integrity, retrieval readiness, and dependency risk.",
    cardKeys: ["doctor", "knowledge_availability", "security_summary"],
  },
];

export function OverviewModule() {
  const overviewQuery = useOverview();
  const { navigateToModule } = useModuleNavigation();

  if (overviewQuery.isPending) {
    return <EmptyState title="Loading overview…" />;
  }
  if (overviewQuery.isError) {
    return <EmptyState title="Could not load overview" body={overviewQuery.error.message} />;
  }

  const cards = deriveOverviewCards(overviewQuery.data);
  const actions = deriveOverviewActions(overviewQuery.data, cards);
  const attentionCount = actions.filter((action) => action.variant !== "ok").length;
  const driftCount =
    Number(overviewQuery.data.drift_flags.claude) + Number(overviewQuery.data.drift_flags.codex);

  return (
    <div className="overview-module">
      <section className="overview-brief">
        <div>
          <span className="module-eyebrow select-none">Operator brief</span>
          <h1>
            {attentionCount === 0
              ? "Workspace steady"
              : `${attentionCount} ${attentionCount === 1 ? "priority" : "priorities"}`}
          </h1>
          <p>
            {attentionCount === 0
              ? "Core config and live sections are in sync."
              : actions[0]?.summary}
          </p>
        </div>
        <dl className="overview-brief__metrics">
          <div data-tone={attentionCount > 0 ? "attention" : "steady"}>
            <dt>Priorities</dt>
            <dd>{attentionCount}</dd>
          </div>
          <div data-tone={driftCount > 0 ? "attention" : "steady"}>
            <dt>Drift lanes</dt>
            <dd>{driftCount}</dd>
          </div>
          <div>
            <dt>Live signals</dt>
            <dd>{cards.length}</dd>
          </div>
        </dl>
      </section>

      <div className="overview-workbench">
        <section className="overview-priority-queue">
          <header className="overview-section-header">
            <div>
              <span className="module-eyebrow">Next actions</span>
              <h2>{attentionCount === 0 ? "Routine scan" : "Attention queue"}</h2>
            </div>
            <span>{actions.length}</span>
          </header>
          <ol>
            {actions.map((action, index) => (
              <li key={action.key}>
                <button type="button" onClick={() => navigateToModule(action.module)}>
                  <span className="overview-priority-queue__rank">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="overview-priority-queue__body">
                    <strong>{action.title}</strong>
                    <small>{action.summary}</small>
                  </span>
                  <StatePill variant={action.variant} label={action.label} />
                  <span className="overview-priority-queue__open" aria-hidden="true">
                    Open
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>

        <section className="overview-alignment">
          <header className="overview-section-header">
            <div>
              <span className="module-eyebrow">Deployment alignment</span>
              <h2>Source to runtime</h2>
            </div>
            <span>{driftCount === 0 ? "aligned" : `${driftCount} changed`}</span>
          </header>
          <div className="overview-alignment__lanes">
            <AlignmentLane
              name="Claude"
              detail="Global instructions, skills, agents, and hooks"
              hasDrift={overviewQuery.data.drift_flags.claude}
              onOpen={() => navigateToModule("config_deploy")}
            />
            <AlignmentLane
              name="Codex"
              detail="Converted skills, templates, and local assets"
              hasDrift={overviewQuery.data.drift_flags.codex}
              onOpen={() => navigateToModule("codex")}
            />
          </div>
        </section>
      </div>

      <section className="overview-signal-ledger">
        <header className="overview-section-header overview-section-header--ledger">
          <div>
            <span className="module-eyebrow">Workspace signals</span>
            <h2>Operational ledger</h2>
          </div>
          <p>Six independent views, grouped by the decision they support.</p>
        </header>
        <div className="overview-signal-ledger__lanes">
          {SIGNAL_LANES.map((lane) => {
            const laneCards = lane.cardKeys
              .map((key) => cards.find((card) => card.key === key))
              .filter((card): card is OverviewCardSummary => card !== undefined);
            return (
              <section key={lane.key} className="overview-signal-lane">
                <header>
                  <div>
                    <h3>{lane.title}</h3>
                    <p>{lane.description}</p>
                  </div>
                  <span>{laneCards.length}</span>
                </header>
                <div>
                  {laneCards.map((card, index) => (
                    <SignalRow
                      key={card.key}
                      card={card}
                      index={index}
                      onOpen={() => navigateToModule(card.deepLinkModule)}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function AlignmentLane({
  name,
  detail,
  hasDrift,
  onOpen,
}: {
  name: string;
  detail: string;
  hasDrift: boolean;
  onOpen: () => void;
}) {
  return (
    <button type="button" onClick={onOpen} aria-label={`Review ${name} deployment`}>
      <span>
        <strong>{name}</strong>
        <small>{detail}</small>
      </span>
      <span className="overview-alignment__track" data-drift={hasDrift} aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <StatePill variant={hasDrift ? "degraded" : "ok"} label={hasDrift ? "drift" : "in sync"} />
    </button>
  );
}

function SignalRow({
  card,
  index,
  onOpen,
}: {
  card: OverviewCardSummary;
  index: number;
  onOpen: () => void;
}) {
  return (
    <button type="button" onClick={onOpen} aria-label={`View ${card.title}`}>
      <span className="overview-signal-row__index">{String(index + 1).padStart(2, "0")}</span>
      <span className="overview-signal-row__identity">
        <strong>{card.title}</strong>
        <small>{card.headline ?? "No summary reported"}</small>
      </span>
      <span className="overview-signal-row__measure">
        <small>measure</small>
        <strong>{card.count ?? "live"}</strong>
      </span>
      <StatePill variant={card.stateVariant ?? "ok"} />
      <span className="overview-signal-row__open" aria-hidden="true">
        View
      </span>
    </button>
  );
}
