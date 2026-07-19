// Left-hand category rail: "All" plus each catalog category, with the server-provided live count.
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

export function CategoryRail({ categories, total, selected, onSelect }: CategoryRailProps) {
  return (
    <nav className="tools-category-rail select-none" aria-label="Tool categories">
      <button
        type="button"
        aria-pressed={selected === null}
        className={
          selected === null
            ? "tools-category-rail__item tools-category-rail__item--active"
            : "tools-category-rail__item"
        }
        onClick={() => onSelect(null)}
      >
        All ({total})
      </button>
      {categories.map((category) => (
        <button
          key={category.name}
          type="button"
          aria-pressed={selected === category.name}
          className={
            selected === category.name
              ? "tools-category-rail__item tools-category-rail__item--active"
              : "tools-category-rail__item"
          }
          onClick={() => onSelect(category.name)}
        >
          {category.name} ({category.count})
        </button>
      ))}
    </nav>
  );
}
