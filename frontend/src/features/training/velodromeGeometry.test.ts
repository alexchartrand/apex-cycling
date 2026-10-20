import { describe, expect, it } from "vitest";
import {
  boxesOverlap,
  buildVelodrome,
  categorizeLoop,
  layoutLabels,
  outwardNormal,
  placeLoops,
  pointAt,
} from "./velodromeGeometry";

const track = buildVelodrome(250);

describe("buildVelodrome", () => {
  it("closes the loop: the last sample returns to the start", () => {
    const first = track.samples[0];
    const last = track.samples[track.samples.length - 1];
    expect(Math.hypot(last.x - first.x, last.y - first.y)).toBeLessThan(0.05);
    expect(last.heading).toBeCloseTo(-2 * Math.PI, 3);
  });

  it("has realistic 250 m proportions (R ≈ 22 m, 40 m straights)", () => {
    expect(track.radiusM).toBeGreaterThan(21);
    expect(track.radiusM).toBeLessThan(24);
    // Curvature is zero across the whole home straight (±20 m around P1).
    expect(pointAt(track, 19).curvature).toBe(0);
    expect(pointAt(track, -19).curvature).toBe(0);
  });

  it("eases curvature in through the transition instead of jumping", () => {
    const k1 = pointAt(track, 25).curvature;
    const k2 = pointAt(track, 30).curvature;
    const kArc = 1 / track.radiusM;
    expect(k1).toBeGreaterThan(0);
    expect(k1).toBeLessThan(k2);
    expect(k2).toBeLessThan(kArc);
    expect(pointAt(track, 250 / 4).curvature).toBeCloseTo(kArc, 6);
  });

  it("runs counterclockwise on screen: right bend first, heading up", () => {
    const apexRight = pointAt(track, 250 / 4); // middle of the first bend
    const apexLeft = pointAt(track, (3 * 250) / 4);
    expect(apexRight.x).toBeGreaterThan(apexLeft.x);
    // Screen y grows downward: at the right apex riders move up (−y).
    expect(Math.sin(apexRight.heading)).toBeCloseTo(-1, 3);
    // The home straight (s = 0) is the bottom of the drawing.
    expect(pointAt(track, 0).y).toBeGreaterThan(pointAt(track, 125).y);
  });

  it("points the outward normal away from the infield", () => {
    const home = pointAt(track, 0);
    expect(outwardNormal(home.heading).y).toBeCloseTo(1); // down, below the home straight
    const apex = pointAt(track, 250 / 4);
    expect(outwardNormal(apex.heading).x).toBeCloseTo(1); // right, outside the right bend
  });
});

describe("placeLoops", () => {
  // Real layout of the Bromont 250 m track (as confirmed by the user):
  // finish 12.5 m after P1; P2 opposite P1; 200/100/50 m markers name the
  // distance remaining to the finish line.
  const loops = [
    { id: "fin", name: "Dép-Arr", distance_m: 0 },
    { id: "p2", name: "P2", distance_m: 112.5 },
    { id: "m200", name: "200m", distance_m: 50 },
    { id: "m50", name: "50m", distance_m: null },
    { id: "p1", name: "P1", distance_m: 237.5 },
    { id: "curve", name: "Courbe 1", distance_m: 60, hidden: true },
  ];

  it("anchors P1 on the home straight and puts P2 exactly opposite", () => {
    const result = placeLoops(loops, 250)!;
    const byId = Object.fromEntries(result.placed.map((p) => [p.id, p]));
    expect(byId.p1.s).toBe(0);
    expect(byId.p2.s).toBe(125);
    const p1 = pointAt(track, byId.p1.s);
    const p2 = pointAt(track, byId.p2.s);
    expect(p2.x).toBeCloseTo(p1.x, 1); // vertically aligned across the infield
  });

  it("puts the finish line 12.5 m after P1, further along the home straight", () => {
    const result = placeLoops(loops, 250)!;
    const finish = result.placed.find((p) => p.id === "fin")!;
    expect(finish.s).toBe(12.5);
    expect(pointAt(track, finish.s).x).toBeGreaterThan(pointAt(track, 0).x);
  });

  it("recovers a missing distance from an 'NNNm' name", () => {
    const result = placeLoops(loops, 250)!;
    expect(result.placed.find((p) => p.id === "m50")!.distanceM).toBe(200);
  });

  it("leaves out loops flagged hidden and categorizes the rest", () => {
    const result = placeLoops(loops, 250)!;
    expect(result.placed.map((p) => p.id)).not.toContain("curve");
    expect(categorizeLoop("Dép-Arr")).toBe("finish");
    expect(categorizeLoop("P1")).toBe("pursuit");
    expect(categorizeLoop("200m")).toBe("distance");
    expect(categorizeLoop("Apex1")).toBe("other");
  });

  it("falls back to the furthest checkpoint without a track length", () => {
    expect(placeLoops([{ id: "a", name: "A", distance_m: 180 }], null)!.lengthM).toBe(180);
    expect(placeLoops([{ id: "a", name: "Apex", distance_m: null }], null)).toBeNull();
  });
});

describe("layoutLabels", () => {
  const req = (id: string, x = 100) => ({ id, anchor: { x, y: 100 }, normal: { x: 0, y: 1 }, width: 40, height: 16 });

  it("slides a colliding label sideways before pushing it further out", () => {
    const [a, b] = layoutLabels([req("a"), req("b", 110)]);
    expect(a.pushedOut).toBe(false);
    expect(b.pushedOut).toBe(true);
    expect(boxesOverlap(a.box, b.box)).toBe(false);
    expect(b.box.y).toBe(a.box.y); // same distance from the track
  });

  it("steps outward once both sides are taken", () => {
    const [a, b, c, d] = layoutLabels([req("a"), req("b"), req("c"), req("d")]);
    for (const [p, q] of [[a, b], [a, c], [a, d], [b, c], [b, d], [c, d]]) {
      expect(boxesOverlap(p.box, q.box)).toBe(false);
    }
    expect(d.box.y).toBeGreaterThan(a.box.y);
  });

  it("keeps the box clear of its anchor on the outward side", () => {
    const [placement] = layoutLabels([{ id: "a", anchor: { x: 0, y: 0 }, normal: { x: 1, y: 0 }, width: 50, height: 16 }]);
    expect(placement.box.x).toBeGreaterThanOrEqual(8);
  });
});
