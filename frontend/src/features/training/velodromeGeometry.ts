/*
  Pure geometry for the velodrome diagram (no DOM), so placement rules are
  unit-tested rather than eyeballed.

  The measurement (black) line is modelled like a real track: two straights
  joined to each bend by clothoid transitions (curvature ramps linearly from
  0 to 1/R, so the banking — and the shading — eases in), a circular arc,
  then a clothoid back out. Proportions for any length C:
    straights 0.16·C each, transitions 0.06·C, bends 0.34·C in total
  → for 250 m: 40 m straights, R ≈ 22.3 m, which is typical of indoor
  250 m tracks.

  Coordinates are screen-style (y down), in meters. Arc length s = 0 is the
  middle of the home (bottom) straight — where pursuit line P1 sits — and s
  increases COUNTERCLOCKWISE on screen, the riders' direction of travel.
*/

export const STRAIGHT_FRACTION = 0.16;
export const TRANSITION_FRACTION = 0.06;

/** Cross-section offsets in meters from the measurement line (+ = outward). */
export const LANE_OFFSETS_M = {
  coteInner: -1.1, // côte d'azur: the pale-blue band below the track's inner edge
  innerEdge: -0.2, // the measurement line is 20 cm above the inner edge
  sprinter: 0.65, // red line, 85 cm above the inner edge
  stayer: 2.13, // blue line, at one third of a 7 m track width
  outerEdge: 6.8, // 7 m track width
};

export type TrackPoint = { x: number; y: number; heading: number; curvature: number };

export type Velodrome = {
  lengthM: number;
  radiusM: number;
  /** Uniformly spaced samples along the measurement line; last ≈ first. */
  samples: (TrackPoint & { s: number })[];
  step: number;
};

/** Signed curvature magnitude at arc length s (0 on straights, 1/R in arcs). */
function curvatureAt(s: number, c: number, r: number): number {
  const half = (STRAIGHT_FRACTION * c) / 2;
  const t = TRANSITION_FRACTION * c;
  const bend = c / 2 - STRAIGHT_FRACTION * c;
  // Position within one half lap (both halves are identical).
  const u = ((s % (c / 2)) + c / 2) % (c / 2);
  if (u < half) return 0;
  const b = u - half; // distance into the bend
  if (b < t) return b / t / r; // clothoid in
  if (b < bend - t) return 1 / r; // arc
  if (b < bend) return (bend - b) / t / r; // clothoid out
  return 0; // second half of the straight
}

export function buildVelodrome(lengthM: number, samplesPerLap = 2000): Velodrome {
  const c = lengthM;
  const t = TRANSITION_FRACTION * c;
  const bend = c / 2 - STRAIGHT_FRACTION * c;
  // Total turn per bend is π: 2 · (t / 2R) from the clothoids + arc / R.
  const radiusM = (bend - t) / Math.PI;
  const step = c / samplesPerLap;

  const samples: Velodrome["samples"] = [];
  let x = 0;
  let y = 0;
  let heading = 0; // moving +x along the bottom straight
  for (let i = 0; i <= samplesPerLap; i++) {
    const s = i * step;
    const k = curvatureAt(s, c, radiusM);
    samples.push({ s, x, y, heading, curvature: k });
    // Midpoint integration. Counterclockwise on a y-down screen = heading
    // decreasing (turning toward -y).
    const kMid = curvatureAt(s + step / 2, c, radiusM);
    const headingMid = heading - (kMid * step) / 2;
    x += Math.cos(headingMid) * step;
    y += Math.sin(headingMid) * step;
    heading -= kMid * step;
  }
  return { lengthM: c, radiusM, samples, step };
}

/** Point on the measurement line at arc length s (wrapped to [0, C)). */
export function pointAt(track: Velodrome, s: number): TrackPoint {
  const c = track.lengthM;
  const wrapped = ((s % c) + c) % c;
  const i = Math.min(Math.floor(wrapped / track.step), track.samples.length - 2);
  const a = track.samples[i];
  const b = track.samples[i + 1];
  const f = (wrapped - a.s) / track.step;
  return {
    x: a.x + (b.x - a.x) * f,
    y: a.y + (b.y - a.y) * f,
    heading: a.heading + (b.heading - a.heading) * f,
    curvature: a.curvature + (b.curvature - a.curvature) * f,
  };
}

/** Outward unit normal (toward the outer edge / away from the infield). */
export function outwardNormal(heading: number): { x: number; y: number } {
  return { x: -Math.sin(heading), y: Math.cos(heading) };
}

export function offsetPoint(point: TrackPoint, offset: number): { x: number; y: number } {
  const n = outwardNormal(point.heading);
  return { x: point.x + n.x * offset, y: point.y + n.y * offset };
}

/** Closed SVG path of the measurement line shifted by `offset` meters, scaled by `scale`. */
export function offsetPath(
  track: Velodrome,
  offset: number,
  scale: number,
  origin: { x: number; y: number },
  everyNth = 4,
): string {
  const parts: string[] = [];
  for (let i = 0; i < track.samples.length - 1; i += everyNth) {
    const p = offsetPoint(track.samples[i], offset);
    parts.push(`${i === 0 ? "M" : "L"}${((p.x - origin.x) * scale).toFixed(2)} ${((p.y - origin.y) * scale).toFixed(2)}`);
  }
  return `${parts.join(" ")} Z`;
}

export function bounds(track: Velodrome, offset: number) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const sample of track.samples) {
    const p = offsetPoint(sample, offset);
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}

// ---------------------------------------------------------------------------
// Timing loops (sqorz checkpoints) → positions on the track
// ---------------------------------------------------------------------------

export type LoopCategory = "pursuit" | "finish" | "distance" | "other";

export function categorizeLoop(name: string): LoopCategory {
  const lower = name.trim().toLowerCase();
  if (lower.includes("dép") || lower.includes("dep-arr") || lower.includes("finish") || lower.includes("arrivée")) {
    return "finish";
  }
  if (/^p\s?[12]\b/.test(lower) || lower.includes("poursuite")) return "pursuit";
  if (NAMED_DISTANCE_PATTERN.test(lower)) return "distance";
  return "other";
}

export function isPursuitOne(name: string): boolean {
  const lower = name.trim().toLowerCase();
  return /^p\s?1\b/.test(lower) || /poursuite\s*1\b/.test(lower);
}

/** "200m" / "50 m" style split markers name the REMAINING distance to the finish line. */
export const NAMED_DISTANCE_PATTERN = /^(\d+(?:\.\d+)?)\s*m$/i;

export type LoopInput = { id: string; name: string; distance_m: number | null; hidden?: boolean };
export type PlacedLoop = { id: string; name: string; category: LoopCategory; distanceM: number; s: number };

/**
 * Places loops on the diagram (loops flagged `hidden` — a per-track setting —
 * are left out entirely, including from the furthest-distance length fallback):
 *  - track length is the manually set `lengthM`, else the furthest reported
 *    checkpoint distance (a rough fallback — sqorz never reports length);
 *  - a missing `distance_m` is recovered from "NNNm" names (remaining
 *    distance to the finish), otherwise the loop can't be placed;
 *  - everything is rotated so P1 sits at s = 0 (middle of the home
 *    straight), which also puts P2 exactly opposite.
 */
export function placeLoops(
  loops: LoopInput[],
  lengthM: number | null | undefined,
): { lengthM: number; placed: PlacedLoop[] } | null {
  const visible = loops.filter((loop) => !loop.hidden);
  const total =
    lengthM ||
    visible.reduce((max, loop) => (loop.distance_m != null ? Math.max(max, loop.distance_m) : max), 0) ||
    null;
  if (!total) return null;

  const resolved = visible.flatMap((loop) => {
    if (loop.distance_m != null) return [{ loop, distance: loop.distance_m }];
    const match = NAMED_DISTANCE_PATTERN.exec(loop.name.trim());
    return match ? [{ loop, distance: total - Number(match[1]) }] : [];
  });
  if (resolved.length === 0) return null;

  const anchor = resolved.find((r) => isPursuitOne(r.loop.name))?.distance ?? 0;
  return {
    lengthM: total,
    placed: resolved.map(({ loop, distance }) => ({
      id: loop.id,
      name: loop.name,
      category: categorizeLoop(loop.name),
      distanceM: distance,
      s: (((distance - anchor) % total) + total) % total,
    })),
  };
}

// ---------------------------------------------------------------------------
// Label layout
// ---------------------------------------------------------------------------

export type Box = { x: number; y: number; width: number; height: number };

export function boxesOverlap(a: Box, b: Box, gap = 3): boolean {
  return a.x < b.x + b.width + gap && b.x < a.x + a.width + gap && a.y < b.y + b.height + gap && b.y < a.y + a.height + gap;
}

export type LabelRequest = { id: string; anchor: { x: number; y: number }; normal: { x: number; y: number }; width: number; height: number };
export type LabelPlacement = { id: string; box: Box; pushedOut: boolean };

/**
 * Greedy placement: each label starts just beyond its anchor (the marker's
 * outer end), offset along the outward normal so the box never covers the
 * track. On a collision it first tries sliding sideways (along the track,
 * either way) at the same distance, then steps further out by `stepPx` —
 * sliding first keeps leader lines short and stops them from cutting
 * through a neighbour's label.
 */
export function layoutLabels(requests: LabelRequest[], gapPx = 8, stepPx = 14, maxSteps = 8): LabelPlacement[] {
  const placed: LabelPlacement[] = [];
  for (const req of requests) {
    const tangent = { x: -req.normal.y, y: req.normal.x };
    const reach = (Math.abs(req.normal.x) * req.width) / 2 + (Math.abs(req.normal.y) * req.height) / 2;
    const along = (Math.abs(tangent.x) * req.width) / 2 + (Math.abs(tangent.y) * req.height) / 2;
    const boxAt = (distance: number, shift: number): Box => {
      const cx = req.anchor.x + req.normal.x * (distance + reach) + tangent.x * shift;
      const cy = req.anchor.y + req.normal.y * (distance + reach) + tangent.y * shift;
      return { x: cx - req.width / 2, y: cy - req.height / 2, width: req.width, height: req.height };
    };
    const free = (box: Box) => !placed.some((p) => boxesOverlap(p.box, box));

    let chosen: LabelPlacement | null = null;
    for (let steps = 0; steps <= maxSteps && !chosen; steps++) {
      const distance = gapPx + steps * stepPx;
      // ±2.2 half-widths: a full label width plus a little air.
      for (const shift of [0, along * 2.2, -along * 2.2]) {
        const box = boxAt(distance, shift);
        if (free(box)) {
          chosen = { id: req.id, box, pushedOut: steps > 0 || shift !== 0 };
          break;
        }
      }
    }
    placed.push(chosen ?? { id: req.id, box: boxAt(gapPx + maxSteps * stepPx, 0), pushedOut: true });
  }
  return placed;
}
