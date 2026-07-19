// Tiny inline SVG trend line used inside KPI cards and stat tiles (console redesign).
export interface SparklineProps {
  points: number[];
  width?: number;
  height?: number;
}

const END_DOT_RADIUS = 2.4;
const EDGE_PADDING = 4;

export function Sparkline({ points, width = 88, height = 30 }: SparklineProps) {
  if (points.length < 2) {
    return null;
  }
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const coords = points.map((value, index) => {
    const x = index * (width / (points.length - 1));
    const y = height - EDGE_PADDING - ((value - min) / range) * (height - EDGE_PADDING * 2);
    return [x, y] as const;
  });
  const last = coords[coords.length - 1];
  return (
    <svg
      className="sparkline"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-hidden="true"
    >
      <polyline
        points={coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        opacity={0.9}
      />
      <circle cx={last[0].toFixed(1)} cy={last[1].toFixed(1)} r={END_DOT_RADIUS} fill="currentColor" />
    </svg>
  );
}
