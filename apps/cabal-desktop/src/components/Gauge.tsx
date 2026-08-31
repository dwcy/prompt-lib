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
const VERY_LONG_VALUE_THRESHOLD = 6;

// SVG font-size is in viewBox units, so a fixed value looks fine at the default 170px dial but
// shrinks to unreadable at a compact one (e.g. the 64px dial on the Project Dashboard's health
// cards). Pick a physical caption size that both scales with `size` and shrinks to fit the
// longest known captions (e.g. "not linked", "not authed") without overflowing a small dial.
const CAPTION_MIN_PX = 8;
const CAPTION_MAX_PX = 14;
const CAPTION_WIDTH_MARGIN = 0.9;
const CAPTION_GLYPH_WIDTH_FACTOR = 0.55;

function captionFontSize(caption: string, size: number): number {
  const availableWidth = size * CAPTION_WIDTH_MARGIN;
  const fitPx = availableWidth / (caption.length * CAPTION_GLYPH_WIDTH_FACTOR);
  const physicalPx = Math.min(CAPTION_MAX_PX, Math.max(CAPTION_MIN_PX, fitPx));
  return (physicalPx * VIEWBOX) / size;
}

export function Gauge({ fraction, value, caption, size = 170, tone = "accent" }: GaugeProps) {
  const clamped = Math.min(1, Math.max(0, fraction));
  const fontSize =
    value.length > VERY_LONG_VALUE_THRESHOLD ? 24 : value.length > LONG_VALUE_THRESHOLD ? 30 : 34;
  return (
    <svg
      className={`gauge gauge--${tone}`}
      width={size}
      height={size}
      viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}
      role="img"
      aria-label={caption.length > 0 ? `${value} ${caption}` : value}
    >
      <circle
        className="gauge__track"
        cx={85}
        cy={85}
        r={RADIUS}
        fill="none"
        strokeWidth={STROKE}
      />
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
      {caption.length > 0 ? (
        <text
          className="gauge__caption"
          x={85}
          y={102}
          textAnchor="middle"
          fontSize={captionFontSize(caption, size)}
        >
          {caption}
        </text>
      ) : null}
    </svg>
  );
}
