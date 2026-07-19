// SVG donut gauge with centred value + caption — readiness/services dials (console redesign).
export type GaugeTone = "accent" | "ok" | "info" | "warning" | "danger";

export interface GaugeProps {
  /** 0..1 fill fraction of the ring. */
  fraction: number;
  /** Large centred value, e.g. "81%" or "2/4". */
  value: string;
  /** Small caption under the value, e.g. "ready". */
  caption: string;
  size?: number;
  tone?: GaugeTone;
}

const VIEWBOX = 170;
const RADIUS = 70;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const STROKE = 10;
const LONG_VALUE_THRESHOLD = 3;

export function Gauge({ fraction, value, caption, size = 170, tone = "accent" }: GaugeProps) {
  const clamped = Math.min(1, Math.max(0, fraction));
  const fontSize = value.length > LONG_VALUE_THRESHOLD ? 30 : 34;
  return (
    <svg
      className={`gauge gauge--${tone}`}
      width={size}
      height={size}
      viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}
      role="img"
      aria-label={`${value} ${caption}`}
    >
      <circle className="gauge__track" cx={85} cy={85} r={RADIUS} fill="none" strokeWidth={STROKE} />
      <circle
        className="gauge__fill"
        cx={85}
        cy={85}
        r={RADIUS}
        fill="none"
        strokeWidth={STROKE}
        strokeLinecap="round"
        strokeDasharray={`${(clamped * CIRCUMFERENCE).toFixed(1)} ${CIRCUMFERENCE.toFixed(1)}`}
        transform="rotate(-90 85 85)"
      />
      <text className="gauge__value" x={85} y={80} textAnchor="middle" fontSize={fontSize}>
        {value}
      </text>
      <text className="gauge__caption" x={85} y={102} textAnchor="middle">
        {caption}
      </text>
    </svg>
  );
}
