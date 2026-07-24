import { useEffect, useMemo, useRef, useState } from "react";
import type { TrackLoopSummary } from "./types";
import "./TrackSchema.css";

const VIEW_WIDTH = 640;
const VIEW_HEIGHT = 280;
const MARGIN = 50;
const TRACK_WIDTH = VIEW_WIDTH - MARGIN * 2;
const TRACK_HEIGHT = VIEW_HEIGHT - MARGIN * 2;

const INSET_OUTER = 0;
const INSET_SURFACE = 18;
const LANE_INSETS = [24, 30, 36];
const INSET_INFIELD = 46;
const CENTERLINE_INSET = 32;
const GATE_INNER_REACH = INSET_INFIELD - CENTERLINE_INSET;
const GATE_OUTER_REACH = CENTERLINE_INSET - INSET_OUTER;
const LABEL_GAP = 14;
const LABEL_PADDING_X = 6;
const LABEL_PADDING_Y = 4;

// Loops not surfaced on the schema for now — real sqorz data for this
// track includes duplicate curve checkpoints not shown in the reference
// layout.
const EXCLUDED_LOOP_NAME_PREFIXES = ["courbe"];

const NAMED_DISTANCE_PATTERN = /^(\d+(?:\.\d+)?)\s*m$/i;

function isPursuitOne(name: string): boolean {
  const lower = name.trim().toLowerCase();
  return /^p\s?1\b/.test(lower) || /poursuite\s*1\b/.test(lower);
}

// A "stadium" (pill) outline: two straights joined by semicircle turns,
// traced once starting at the bottom straight's midpoint and going
// counterclockwise (bottom-center -> bottom-right -> right turn -> top
// straight -> left turn -> back to bottom-center) to match the real
// direction of travel on the track. Used to draw each band and — via
// getPointAtLength on the centerline — to place sensor flags
// proportionally along the track by distance_m.
function stadiumPath(inset: number): string {
  const x = MARGIN + inset;
  const y = MARGIN + inset;
  const width = TRACK_WIDTH - inset * 2;
  const height = TRACK_HEIGHT - inset * 2;
  const r = height / 2;
  const top = y;
  const bottom = y + height;
  const capLeft = x + r;
  const capRight = x + width - r;
  const midX = x + width / 2;
  return (
    `M ${midX} ${bottom} L ${capRight} ${bottom} A ${r} ${r} 0 0 0 ${capRight} ${top} ` +
    `L ${capLeft} ${top} A ${r} ${r} 0 0 0 ${capLeft} ${bottom} L ${midX} ${bottom} Z`
  );
}

const BAND_OUTER = stadiumPath(INSET_OUTER);
const BAND_SURFACE = stadiumPath(INSET_SURFACE);
const BAND_INFIELD = stadiumPath(INSET_INFIELD);
const LANE_LINES = LANE_INSETS.map(stadiumPath);
const CENTERLINE = stadiumPath(CENTERLINE_INSET);

type FlagCategory = "pursuit" | "finish" | "distance";

function categorize(name: string): FlagCategory {
  const lower = name.toLowerCase();
  if (lower.includes("dép") || lower.includes("dep-arr") || lower.includes("finish")) return "finish";
  if (lower.startsWith("p1") || lower.startsWith("p2") || lower.includes("poursuite")) return "pursuit";
  return "distance";
}

interface ResolvedLoop {
  loop: TrackLoopSummary;
  distance: number;
}

interface FlagGeometry {
  loop: TrackLoopSummary;
  category: FlagCategory;
  innerX: number;
  innerY: number;
  outerX: number;
  outerY: number;
  labelX: number;
  labelY: number;
}

export function TrackSchema({ loops, lengthM }: { loops: TrackLoopSummary[]; lengthM?: number | null }) {
  const centerlineRef = useRef<SVGPathElement>(null);
  const labelRefs = useRef<Record<string, SVGTextElement | null>>({});
  const [flags, setFlags] = useState<FlagGeometry[]>([]);
  const [labelSizes, setLabelSizes] = useState<Record<string, { width: number; height: number }>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const visibleLoops = useMemo(
    () =>
      loops.filter(
        (loop) => !EXCLUDED_LOOP_NAME_PREFIXES.some((prefix) => loop.name.trim().toLowerCase().startsWith(prefix)),
      ),
    [loops],
  );

  // Total length: prefer the track's manually-set length_m (sqorz never
  // reports true circuit length), else fall back to the furthest reported
  // checkpoint distance.
  const totalDistance = useMemo(() => {
    if (lengthM) return lengthM;
    const max = visibleLoops.reduce((acc, loop) => (loop.distance_m != null ? Math.max(acc, loop.distance_m) : acc), 0);
    return max || null;
  }, [visibleLoops, lengthM]);

  // Sqorz sometimes omits a checkpoint's distance_m — but named split
  // markers ("50m", "100m", ...) encode remaining distance to the
  // start/finish line, so their true cumulative distance can be recovered
  // as totalDistance - name once totalDistance is known.
  const resolvedLoops = useMemo<ResolvedLoop[]>(() => {
    if (!totalDistance) return [];
    return visibleLoops.flatMap((loop) => {
      if (loop.distance_m != null) return [{ loop, distance: loop.distance_m }];
      const match = loop.name.trim().match(NAMED_DISTANCE_PATTERN);
      if (!match) return [];
      return [{ loop, distance: totalDistance - Number(match[1]) }];
    });
  }, [visibleLoops, totalDistance]);

  // The pursuit line sits at the exact midpoint of the home straight — used
  // to anchor the diagram (rather than the start/finish line, which sits
  // slightly off-center) so the drawing lines up with the physical track.
  const anchorDistance = useMemo(() => {
    const anchor = resolvedLoops.find((r) => isPursuitOne(r.loop.name));
    return anchor?.distance ?? 0;
  }, [resolvedLoops]);

  useEffect(() => {
    const path = centerlineRef.current;
    if (!path || resolvedLoops.length === 0 || !totalDistance) {
      setFlags([]);
      return;
    }
    const pathLength = path.getTotalLength();
    const eps = 0.5;
    setFlags(
      resolvedLoops.map(({ loop, distance }) => {
        const fraction = (((distance - anchorDistance) % totalDistance) + totalDistance) % totalDistance / totalDistance;
        const len = fraction * pathLength;
        const { x, y } = path.getPointAtLength(len);
        const before = path.getPointAtLength(Math.max(0, len - eps));
        const after = path.getPointAtLength(Math.min(pathLength, len + eps));
        const tangentX = after.x - before.x;
        const tangentY = after.y - before.y;
        const tangentLength = Math.hypot(tangentX, tangentY) || 1;
        const normalX = -tangentY / tangentLength;
        const normalY = tangentX / tangentLength;
        return {
          loop,
          category: categorize(loop.name),
          innerX: x - normalX * GATE_INNER_REACH,
          innerY: y - normalY * GATE_INNER_REACH,
          outerX: x + normalX * GATE_OUTER_REACH,
          outerY: y + normalY * GATE_OUTER_REACH,
          labelX: x + normalX * (GATE_OUTER_REACH + LABEL_GAP),
          labelY: y + normalY * (GATE_OUTER_REACH + LABEL_GAP),
        };
      }),
    );
  }, [resolvedLoops, anchorDistance, totalDistance]);

  useEffect(() => {
    const sizes: Record<string, { width: number; height: number }> = {};
    for (const flag of flags) {
      const el = labelRefs.current[flag.loop.id];
      if (el) {
        const box = el.getBBox();
        sizes[flag.loop.id] = { width: box.width, height: box.height };
      }
    }
    setLabelSizes(sizes);
  }, [flags]);

  if (resolvedLoops.length === 0) return null;

  return (
    <svg
      className="track-schema"
      viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
      width="100%"
      role="img"
      aria-label="Track sensor layout"
    >
      <defs>
        <linearGradient id="track-schema-wood" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--track-wood-1)" />
          <stop offset="100%" stopColor="var(--track-wood-2)" />
        </linearGradient>
      </defs>
      <path d={BAND_OUTER} fill="url(#track-schema-wood)" stroke="var(--track-wood-2)" />
      <path className="track-schema__band--surface" d={BAND_SURFACE} />
      {LANE_LINES.map((d, i) => (
        <path key={i} className="track-schema__lane" d={d} />
      ))}
      <path className="track-schema__band--infield" d={BAND_INFIELD} />
      <path ref={centerlineRef} d={CENTERLINE} fill="none" stroke="none" />
      {flags.map((flag) => {
        const { loop, category, innerX, innerY, outerX, outerY, labelX, labelY } = flag;
        const size = labelSizes[loop.id];
        const isSelected = selectedId === loop.id;
        return (
          <g
            key={loop.id}
            className={`track-schema__flag track-schema__flag--${category}${isSelected ? " track-schema__flag--selected" : ""}`}
            role="button"
            tabIndex={0}
            aria-pressed={isSelected}
            onClick={() => setSelectedId((current) => (current === loop.id ? null : loop.id))}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setSelectedId((current) => (current === loop.id ? null : loop.id));
              }
            }}
          >
            <line className="track-schema__leader" x1={outerX} y1={outerY} x2={labelX} y2={labelY} />
            <line className="track-schema__gate" x1={innerX} y1={innerY} x2={outerX} y2={outerY} />
            {size && (
              <rect
                className="track-schema__label-bg"
                x={labelX - size.width / 2 - LABEL_PADDING_X}
                y={labelY - size.height / 2 - LABEL_PADDING_Y}
                width={size.width + LABEL_PADDING_X * 2}
                height={size.height + LABEL_PADDING_Y * 2}
                rx={size.height / 2 + LABEL_PADDING_Y}
              />
            )}
            <text
              ref={(el) => {
                labelRefs.current[loop.id] = el;
              }}
              className="track-schema__label"
              x={labelX}
              y={labelY}
              textAnchor="middle"
              dominantBaseline="middle"
              opacity={size ? 1 : 0}
            >
              {loop.name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
