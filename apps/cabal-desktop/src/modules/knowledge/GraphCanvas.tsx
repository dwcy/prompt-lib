// Radial SVG graph canvas: positions nodes by type ring, supports zoom, node selection, and
// edge selection (click a line to inspect its routing evidence in the drawer).
import { useMemo, useState } from "react";
import type { KnowledgeEdge, KnowledgeGraph, KnowledgeNode } from "@/api/knowledge";
import { nodeTypeClass } from "@/modules/knowledge/graphNodeColors";

interface GraphCanvasProps {
  graph: KnowledgeGraph;
  selectedId: string | null;
  selectedEdgeId: string | null;
  onSelect: (node: KnowledgeNode) => void;
  onSelectEdge: (edge: KnowledgeEdge) => void;
  highlight: string;
}

interface PositionedNode extends KnowledgeNode {
  x: number;
  y: number;
  radius: number;
}

const WIDTH = 1100;
const HEIGHT = 680;
const CENTER_X = WIDTH / 2;
const CENTER_Y = HEIGHT / 2;

export function GraphCanvas({
  graph,
  selectedId,
  selectedEdgeId,
  onSelect,
  onSelectEdge,
  highlight,
}: GraphCanvasProps) {
  const [scale, setScale] = useState(1);
  const layout = useMemo(() => positionNodes(graph.nodes), [graph.nodes]);
  const nodeById = useMemo(() => new Map(layout.map((node) => [node.id, node])), [layout]);
  const query = highlight.trim().toLowerCase();

  if (!graph.available) {
    return (
      <div className="km-graph__empty">
        <strong>No OKF graph exported</strong>
        <span>Use Export bundle, then rebuild the index.</span>
      </div>
    );
  }

  if (layout.length === 0) {
    return (
      <div className="km-graph__empty">
        <strong>No concepts match these filters</strong>
        <span>Clear the graph filters to restore the map.</span>
      </div>
    );
  }

  return (
    <>
      <div className="km-graph__zoom">
        <label>
          Zoom
          <input
            type="range"
            min="0.65"
            max="1.35"
            step="0.05"
            value={scale}
            onChange={(event) => setScale(Number(event.target.value))}
          />
        </label>
      </div>
      <svg
        className="km-graph__surface"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Knowledge graph"
      >
        <g
          transform={`translate(${CENTER_X} ${CENTER_Y}) scale(${scale}) translate(${-CENTER_X} ${-CENTER_Y})`}
        >
          <g className="km-graph__edges">
            {graph.edges.map((edge) => {
              const from = nodeById.get(edge.from);
              const to = nodeById.get(edge.to);
              if (from === undefined || to === undefined) return null;
              const active = edge.id === selectedEdgeId;
              const touchesSelection = selectedId === edge.from || selectedId === edge.to;
              return (
                // biome-ignore lint/a11y/useSemanticElements: SVG line cannot be a native <button>; keyboard/aria handled manually
                <line
                  key={edge.id}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  className={active ? "is-selected" : touchesSelection ? "is-active" : undefined}
                  role="button"
                  tabIndex={0}
                  aria-label={`${edge.relation}: ${from.label} to ${to.label}`}
                  onClick={() => onSelectEdge(edge)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectEdge(edge);
                    }
                  }}
                />
              );
            })}
          </g>
          <g className="km-graph__nodes">
            {layout.map((node) => {
              const active = node.id === selectedId;
              const matched =
                query.length > 0 &&
                (node.id.toLowerCase().includes(query) ||
                  node.label.toLowerCase().includes(query) ||
                  node.resource.toLowerCase().includes(query));
              return (
                <foreignObject
                  key={node.id}
                  x={node.x - node.radius}
                  y={node.y - node.radius}
                  width={node.radius * 2}
                  height={node.radius * 2}
                >
                  <button
                    type="button"
                    className={`km-node km-node--${nodeTypeClass(node.type)}${active ? " is-active" : ""}${matched ? " is-matched" : ""}`}
                    onClick={() => onSelect(node)}
                    aria-label={node.label}
                    style={{ width: node.radius * 2, height: node.radius * 2 }}
                  >
                    <span>{node.type.slice(0, 2).toUpperCase()}</span>
                  </button>
                </foreignObject>
              );
            })}
          </g>
          <g className="km-graph__labels">
            {layout
              .filter((node) => node.id === selectedId || node.radius >= 16)
              .map((node) => (
                <text key={node.id} x={node.x + node.radius + 5} y={node.y + 4}>
                  {shortLabel(node.label)}
                </text>
              ))}
          </g>
        </g>
      </svg>
    </>
  );
}

function positionNodes(nodes: KnowledgeNode[]): PositionedNode[] {
  const groups = new Map<string, KnowledgeNode[]>();
  for (const node of nodes) {
    const group = groups.get(node.type) ?? [];
    group.push(node);
    groups.set(node.type, group);
  }
  const typeEntries = [...groups.entries()].sort(([left], [right]) => left.localeCompare(right));
  const ringGap = Math.max(70, Math.min(126, 460 / Math.max(typeEntries.length, 1)));
  const positioned: PositionedNode[] = [];
  typeEntries.forEach(([, group], groupIndex) => {
    const radius = 86 + groupIndex * ringGap;
    const start = (groupIndex % 2) * 0.27;
    group.forEach((node, index) => {
      const angle = start + (Math.PI * 2 * index) / Math.max(group.length, 1);
      const incoming = Number(node.metrics.incoming ?? 0);
      const outgoing = Number(node.metrics.outgoing ?? 0);
      positioned.push({
        ...node,
        x: CENTER_X + Math.cos(angle) * radius,
        y: CENTER_Y + Math.sin(angle) * radius * 0.72,
        radius: Math.max(9, Math.min(22, 10 + Math.sqrt(incoming + outgoing) * 2)),
      });
    });
  });
  return positioned;
}

function shortLabel(label: string) {
  return label.length > 28 ? `${label.slice(0, 25)}...` : label;
}
