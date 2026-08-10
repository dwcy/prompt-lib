// Top-left overlay legend for the graph canvas: one colored dot per node type actually present.
import {
  nodeTypeClass,
  nodeTypeStyle,
  orderedPresentTypes,
} from "@/modules/knowledge/graphNodeColors";

export interface GraphLegendProps {
  types: string[];
}

export function GraphLegend({ types }: GraphLegendProps) {
  const ordered = orderedPresentTypes(types);
  if (ordered.length === 0) return null;

  return (
    <div className="km-graph__legend" aria-hidden="true">
      {ordered.map((type) => {
        const style = nodeTypeStyle(type);
        return (
          <span key={type} className={`km-graph__legend-item km-node--${nodeTypeClass(type)}`}>
            <span className="km-graph__legend-dot" />
            {style.label}
          </span>
        );
      })}
    </div>
  );
}
