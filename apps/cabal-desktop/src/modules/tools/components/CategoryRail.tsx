// Left console rail: "All" plus each catalog category as a full-width button with a proportional
// mini count bar and mono count; the selected entry gets the sidebar's active-accent treatment.
export interface CategoryRailEntry {
  name: string;
  count: number;
}

export interface CategoryRailProps {
  categories: CategoryRailEntry[];
  total: number;
  selected: string | null;
  onSelect: (category: string | null) => void;
}

const MAX_BAR_WIDTH_PX = 34;
const MIN_BAR_WIDTH_PX = 2;

export function CategoryRail({ categories, total, selected, onSelect }: CategoryRailProps) {
  const maxCount = categories.reduce((max, category) => Math.max(max, category.count), 1);
  return (
    <nav className="tools-console__rail select-none" aria-label="Tool categories">
      <RailItem
        label="All"
        count={total}
        barWidth={MAX_BAR_WIDTH_PX}
        active={selected === null}
        onClick={() => onSelect(null)}
      />
      {categories.map((category) => (
        <RailItem
          key={category.name}
          label={category.name}
          count={category.count}
          barWidth={barWidth(category.count, maxCount)}
          active={selected === category.name}
          onClick={() => onSelect(category.name)}
        />
      ))}
    </nav>
  );
}

interface RailItemProps {
  label: string;
  count: number;
  barWidth: number;
  active: boolean;
  onClick: () => void;
}

function RailItem({ label, count, barWidth, active, onClick }: RailItemProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      aria-label={`${label} (${count})`}
      className={
        active
          ? "tools-console__rail-item tools-console__rail-item--active"
          : "tools-console__rail-item"
      }
      onClick={onClick}
    >
      <span className="tools-console__rail-name">{label}</span>
      <span className="tools-console__rail-meter">
        {/* Width is proportional to the live count — runtime-computed, so inline by necessity. */}
        <span
          className="tools-console__rail-bar"
          style={{ width: `${barWidth}px` }}
          aria-hidden="true"
        />
        <span className="tools-console__rail-count">{count}</span>
      </span>
    </button>
  );
}

function barWidth(count: number, maxCount: number): number {
  return Math.min(
    MAX_BAR_WIDTH_PX,
    Math.max(MIN_BAR_WIDTH_PX, Math.round((count / maxCount) * MAX_BAR_WIDTH_PX)),
  );
}
