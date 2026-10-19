import { useMemo, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { useElementWidth } from "../../hooks/useElementWidth";
import { useFormat } from "../../i18n/useFormat";
import type { TrackLoopSummary } from "./types";
import {
  bounds,
  buildVelodrome,
  LANE_OFFSETS_M,
  layoutLabels,
  offsetPath,
  offsetPoint,
  outwardNormal,
  placeLoops,
  pointAt,
  type LoopCategory,
  type PlacedLoop,
  type Velodrome,
} from "./velodromeGeometry";
import "./VelodromeDiagram.css";

// Loops not drawn for now: real sqorz data for the Bromont track has extra
// "Courbe 1/2" checkpoints that aren't part of the reference layout.
// Becomes a per-track setting in T3.5.
const DEFAULT_HIDDEN_PREFIXES = ["courbe"];

const CATEGORY_COLORS: Record<LoopCategory, string> = {
  pursuit: "var(--color-marker)",
  finish: "var(--color-text)",
  distance: "var(--color-highlight)",
  other: "var(--color-accent)",
};

const LABEL_FONT_PX = 12;
const LABEL_HEIGHT = 22;
const BANKING_LEVELS = 12;

type Variant = "full" | "mini";

type Props = {
  loops: TrackLoopSummary[];
  lengthM: number | null | undefined;
  hiddenLoopPrefixes?: string[];
  /** Controlled selection; omit to let the diagram manage it. */
  selectedLoopId?: string | null;
  onSelectLoop?: (loopId: string | null) => void;
  variant?: Variant;
};

/** Rough label width without measuring the DOM (keeps layout pure and testable). */
function estimateLabelWidth(text: string): number {
  return Math.ceil(text.length * LABEL_FONT_PX * 0.6) + 18;
}

type Layout = {
  scale: number;
  widthFactor: number;
  origin: { x: number; y: number };
  viewBox: string;
};

/**
 * Chooses a px/m scale so the track fills the container (leaving room for
 * labels), and widens the 7 m track band on small screens so it stays
 * legible. Lane offsets are multiplied by `widthFactor`; the measurement
 * line — where loops are positioned — is never distorted.
 */
function computeLayout(track: Velodrome, containerWidth: number, variant: Variant): Layout {
  const labelMargin = variant === "mini" ? 2 : Math.min(84, Math.max(48, containerWidth * 0.12));
  const minTrackPx = variant === "mini" ? 7 : containerWidth < 520 ? 22 : 30;
  const centerBounds = bounds(track, 0);
  let widthFactor = 1;
  let scale = 1;
  for (let i = 0; i < 2; i++) {
    const outerReach = LANE_OFFSETS_M.outerEdge * widthFactor;
    scale = (containerWidth - 2 * labelMargin) / (centerBounds.width + 2 * outerReach);
    widthFactor = Math.max(1, minTrackPx / ((LANE_OFFSETS_M.outerEdge - LANE_OFFSETS_M.coteInner) * scale));
  }
  const outerReach = LANE_OFFSETS_M.outerEdge * widthFactor;
  const origin = { x: centerBounds.minX - outerReach, y: centerBounds.minY - outerReach };
  const w = (centerBounds.width + 2 * outerReach) * scale;
  const h = (centerBounds.height + 2 * outerReach) * scale;
  return { scale, widthFactor, origin, viewBox: `0 0 ${w} ${h}` };
}

function bankingPaths(track: Velodrome, layout: Layout): string[] {
  const kMax = 1 / track.radiusM;
  const inner = LANE_OFFSETS_M.innerEdge * layout.widthFactor;
  const outer = LANE_OFFSETS_M.outerEdge * layout.widthFactor;
  const toPx = (p: { x: number; y: number }) =>
    `${((p.x - layout.origin.x) * layout.scale).toFixed(1)} ${((p.y - layout.origin.y) * layout.scale).toFixed(1)}`;
  const levels: string[][] = Array.from({ length: BANKING_LEVELS }, () => []);
  const stride = 2;
  for (let i = 0; i + stride < track.samples.length; i += stride) {
    const a = track.samples[i];
    const b = track.samples[i + stride];
    const level = Math.round(((a.curvature + b.curvature) / 2 / kMax) * BANKING_LEVELS);
    if (level <= 0) continue;
    levels[Math.min(level, BANKING_LEVELS) - 1].push(
      `M${toPx(offsetPoint(a, inner))} L${toPx(offsetPoint(b, inner))} L${toPx(offsetPoint(b, outer))} L${toPx(offsetPoint(a, outer))} Z`,
    );
  }
  return levels.map((quads) => quads.join(" "));
}

export function VelodromeDiagram({
  loops,
  lengthM,
  hiddenLoopPrefixes = DEFAULT_HIDDEN_PREFIXES,
  selectedLoopId,
  onSelectLoop,
  variant = "full",
}: Props) {
  const { t } = useTranslation("training");
  const fmt = useFormat();
  const { ref, width } = useElementWidth<HTMLDivElement>(variant === "mini" ? 160 : 640);
  const [internalSelected, setInternalSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const selected = selectedLoopId !== undefined ? selectedLoopId : internalSelected;

  const placement = useMemo(() => placeLoops(loops, lengthM, hiddenLoopPrefixes), [loops, lengthM, hiddenLoopPrefixes]);
  const track = useMemo(() => (placement ? buildVelodrome(placement.lengthM) : null), [placement]);
  const layout = useMemo(() => (track ? computeLayout(track, width, variant) : null), [track, width, variant]);

  const drawing = useMemo(() => {
    if (!track || !layout || !placement) return null;
    const f = layout.widthFactor;
    const path = (offset: number) => offsetPath(track, offset * f, layout.scale, layout.origin);
    const px = (p: { x: number; y: number }) => ({
      x: (p.x - layout.origin.x) * layout.scale,
      y: (p.y - layout.origin.y) * layout.scale,
    });

    const markers = [...placement.placed]
      .sort((a, b) => a.s - b.s)
      .map((loop) => {
        const point = pointAt(track, loop.s);
        const normal = outwardNormal(point.heading);
        return {
          loop,
          normal,
          inner: px(offsetPoint(point, LANE_OFFSETS_M.coteInner * f)),
          outer: px(offsetPoint(point, LANE_OFFSETS_M.outerEdge * f)),
          onLine: px(point),
        };
      });

    const labels =
      variant === "full"
        ? layoutLabels(
            markers.map((m) => ({
              id: m.loop.id,
              anchor: m.outer,
              normal: m.normal,
              width: estimateLabelWidth(m.loop.name),
              height: LABEL_HEIGHT,
            })),
          )
        : [];

    // Direction-of-travel arrow in the infield, along the home straight.
    const arrowOffset = (LANE_OFFSETS_M.coteInner - 3) * f;
    const arrowFrom = px(offsetPoint(pointAt(track, -9), arrowOffset));
    const arrowTo = px(offsetPoint(pointAt(track, 9), arrowOffset));

    return {
      infield: path(LANE_OFFSETS_M.coteInner),
      cote: `${path(LANE_OFFSETS_M.coteInner)} ${path(LANE_OFFSETS_M.innerEdge)}`,
      surface: `${path(LANE_OFFSETS_M.innerEdge)} ${path(LANE_OFFSETS_M.outerEdge)}`,
      banking: bankingPaths(track, layout),
      measure: path(0),
      sprinter: path(LANE_OFFSETS_M.sprinter),
      stayer: path(LANE_OFFSETS_M.stayer),
      markers,
      labels,
      arrow: { from: arrowFrom, to: arrowTo },
    };
  }, [track, layout, placement, variant]);

  if (!placement || !drawing || !layout) return null;

  // Grow the viewBox to fit labels that stick out past the track.
  const [, , baseW, baseH] = layout.viewBox.split(" ").map(Number);
  let minX = 0;
  let minY = 0;
  let maxX = baseW;
  let maxY = baseH;
  for (const label of drawing.labels) {
    minX = Math.min(minX, label.box.x - 4);
    minY = Math.min(minY, label.box.y - 4);
    maxX = Math.max(maxX, label.box.x + label.box.width + 4);
    maxY = Math.max(maxY, label.box.y + label.box.height + 4);
  }
  const viewBox = `${minX} ${minY} ${maxX - minX} ${maxY - minY}`;

  function toggle(loop: PlacedLoop) {
    const next = selected === loop.id ? null : loop.id;
    if (selectedLoopId === undefined) setInternalSelected(next);
    onSelectLoop?.(next);
  }

  function onKey(event: KeyboardEvent, loop: PlacedLoop) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggle(loop);
    }
  }

  const categories = [...new Set(placement.placed.map((p) => p.category))];
  const labelById = Object.fromEntries(drawing.labels.map((l) => [l.id, l]));
  const interactive = variant === "full";

  return (
    <figure className={`velodrome velodrome--${variant}`} ref={ref}>
      <svg
        viewBox={viewBox}
        width="100%"
        role="img"
        aria-label={t("diagram.label", { count: placement.placed.length })}
        className="velodrome__svg"
      >
        <path className="velodrome__infield" d={drawing.infield} />
        <path className="velodrome__cote" d={drawing.cote} fillRule="evenodd" />
        <path className="velodrome__surface" d={drawing.surface} fillRule="evenodd" />
        {drawing.banking.map((d, i) => (
          <path key={i} className="velodrome__banking" d={d} style={{ fillOpacity: ((i + 1) / BANKING_LEVELS) * 0.55 }} />
        ))}
        {variant === "full" && (
          <>
            <path className="velodrome__line velodrome__line--stayer" d={drawing.stayer} />
            <path className="velodrome__line velodrome__line--sprinter" d={drawing.sprinter} />
          </>
        )}
        <path className="velodrome__line velodrome__line--measure" d={drawing.measure} />

        {variant === "full" && (
          <g className="velodrome__direction" aria-hidden>
            <defs>
              <marker id="velodrome-arrowhead" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M0 0 L10 5 L0 10 z" />
              </marker>
            </defs>
            <line
              x1={drawing.arrow.from.x}
              y1={drawing.arrow.from.y}
              x2={drawing.arrow.to.x}
              y2={drawing.arrow.to.y}
              markerEnd="url(#velodrome-arrowhead)"
            />
            <text x={(drawing.arrow.from.x + drawing.arrow.to.x) / 2} y={drawing.arrow.from.y - 8} textAnchor="middle">
              {t("diagram.direction")}
            </text>
          </g>
        )}

        {drawing.markers.map(({ loop, inner, outer, onLine }) => {
          const label = labelById[loop.id];
          const isActive = selected === loop.id || hovered === loop.id;
          const color = CATEGORY_COLORS[loop.category];
          return (
            <g
              key={loop.id}
              className={[
                "velodrome__marker",
                selected === loop.id && "velodrome__marker--selected",
                isActive && "velodrome__marker--active",
              ]
                .filter(Boolean)
                .join(" ")}
              style={{ ["--marker-color" as string]: color }}
              {...(interactive
                ? {
                    role: "button",
                    tabIndex: 0,
                    "aria-pressed": selected === loop.id,
                    "aria-label": t("diagram.loopAria", { name: loop.name, distance: fmt.distance(loop.distanceM) }),
                    onClick: () => toggle(loop),
                    onKeyDown: (e: KeyboardEvent) => onKey(e, loop),
                    onMouseEnter: () => setHovered(loop.id),
                    onMouseLeave: () => setHovered(null),
                    onFocus: () => setHovered(loop.id),
                    onBlur: () => setHovered(null),
                  }
                : {})}
            >
              {/* Wide invisible hit area so thin ticks are easy to tap. */}
              <line className="velodrome__hit" x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} />
              <line className="velodrome__tick" x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} />
              <circle className="velodrome__dot" cx={onLine.x} cy={onLine.y} r={variant === "mini" ? 1.8 : 3} />
              {label && (
                <>
                  {label.pushedOut && (
                    <line
                      className="velodrome__leader"
                      x1={outer.x}
                      y1={outer.y}
                      x2={label.box.x + label.box.width / 2}
                      y2={label.box.y + label.box.height / 2}
                    />
                  )}
                  <rect
                    className="velodrome__label-bg"
                    x={label.box.x}
                    y={label.box.y}
                    width={label.box.width}
                    height={label.box.height}
                    rx={label.box.height / 2}
                  />
                  <text
                    className="velodrome__label"
                    x={label.box.x + label.box.width / 2}
                    y={label.box.y + label.box.height / 2}
                    textAnchor="middle"
                    dominantBaseline="central"
                  >
                    {loop.name}
                  </text>
                </>
              )}
            </g>
          );
        })}
      </svg>
      {variant === "full" && (
        <figcaption className="velodrome__legend">
          {categories.map((category) => (
            <span key={category} className="velodrome__legend-item">
              <span className="velodrome__legend-swatch" style={{ background: CATEGORY_COLORS[category] }} />
              {t(`diagram.categories.${category}`)}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}
