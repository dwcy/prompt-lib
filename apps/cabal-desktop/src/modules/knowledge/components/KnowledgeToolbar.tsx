// Graph tab toolbar: search + type/relation filters + reset, right-aligned mono node/edge counts.
import type { KnowledgeGraphFilters } from "@/api/knowledge";

export interface KnowledgeToolbarProps {
  filters: KnowledgeGraphFilters;
  onFiltersChange: (filters: KnowledgeGraphFilters) => void;
  typeOptions: string[];
  relationOptions: string[];
  nodeCount: number;
  edgeCount: number;
}

export function KnowledgeToolbar({
  filters,
  onFiltersChange,
  typeOptions,
  relationOptions,
  nodeCount,
  edgeCount,
}: KnowledgeToolbarProps) {
  return (
    <div className="km-toolbar">
      <input
        type="search"
        className="km-toolbar__search"
        placeholder="Search concepts, routes, evidence…"
        autoComplete="off"
        value={filters.query}
        onChange={(event) => onFiltersChange({ ...filters, query: event.target.value })}
      />
      <select
        aria-label="Concept type"
        className="km-toolbar__select"
        value={filters.type}
        onChange={(event) => onFiltersChange({ ...filters, type: event.target.value })}
      >
        <option value="">All types</option>
        {typeOptions.map((type) => (
          <option key={type} value={type}>
            {type}
          </option>
        ))}
      </select>
      <select
        aria-label="Relation kind"
        className="km-toolbar__select"
        value={filters.relation}
        onChange={(event) => onFiltersChange({ ...filters, relation: event.target.value })}
      >
        <option value="">All relations</option>
        {relationOptions.map((relation) => (
          <option key={relation} value={relation}>
            {relation}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="km-toolbar__reset"
        onClick={() => onFiltersChange({ query: "", type: "", relation: "" })}
      >
        Reset
      </button>
      <span className="km-toolbar__counts">
        {nodeCount} nodes · {edgeCount} edges
      </span>
    </div>
  );
}
