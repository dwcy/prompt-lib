// Activity card: the prioritized attention queue rendered as an event feed — severity glyph,
// title/summary, mono meta line — with per-row deep links and a diagnostics footer link.
import type { ModuleKey } from "@/modules/registry";
import type { OverviewActivityItem } from "../overviewConsole";

export interface ActivityCardProps {
  items: OverviewActivityItem[];
  onOpen: (module: ModuleKey) => void;
  onOpenDiagnostics: () => void;
}

export function ActivityCard({ items, onOpen, onOpenDiagnostics }: ActivityCardProps) {
  return (
    <section className="overview-card overview-activity" aria-label="Activity">
      <header className="overview-card__header">
        <b>Activity</b>
        <span>next actions</span>
      </header>
      <div className="overview-activity__list">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            className="overview-activity__row select-none"
            onClick={() => onOpen(item.module)}
            aria-label={`Open ${item.title}`}
          >
            <span className="overview-activity__glyph" data-tone={item.tone} aria-hidden="true">
              {item.glyph}
            </span>
            <span className="overview-activity__body">
              <b>{item.title}</b> — {item.summary}
              <span className="overview-activity__meta">{item.meta}</span>
            </span>
          </button>
        ))}
      </div>
      <footer className="overview-activity__footer">
        <span>
          {items.length} {items.length === 1 ? "action" : "actions"} queued
        </span>
        <button
          type="button"
          className="overview-activity__link select-none"
          onClick={onOpenDiagnostics}
        >
          View diagnostics →
        </button>
      </footer>
    </section>
  );
}
