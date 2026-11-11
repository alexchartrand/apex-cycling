import { describe, expect, it, vi } from "vitest";
import { createFormatters } from "../../i18n/format";
import type { WorkoutItem, WorkoutStep } from "./types";
import {
  bestTimes,
  CARD_LAYOUTS,
  clipText,
  drawWorkoutCard,
  fitRows,
  powerText,
  workoutCardFileName,
  workoutCardModel,
  wrapText,
  type WorkoutCardInput,
  type WorkoutCardRow,
  type WorkoutCardTexts,
} from "./workoutCard";

const fmt = createFormatters("en");

const texts: WorkoutCardTexts = {
  brand: "ApexCycling",
  kind: (kind) => ({ warmup: "Warm-up", work: "Effort", recovery: "Recovery", cooldown: "Cool-down" })[kind],
  repeat: (count) => `${count} ×`,
  laps: (count) => (count === 1 ? "1 lap" : `${count} laps`),
  open: "Lap",
  event: (key) => ({ f200: "Flying 200 m", "500m": "500 m" })[key as "f200"] ?? key,
  start: (start) => (start === "standing" ? "Standing start" : "Flying start"),
  rpe: (value) => `RPE ${value}`,
  best: (time) => `best ${time}`,
  tss: (value) => `${value} TSS`,
  ftp: (watts) => `Watts at FTP ${watts} W`,
  noFtp: "Power in % FTP",
  units: { ftpPct: "% FTP", w: "W", rpm: "rpm" },
};

function step(over: Partial<WorkoutStep>): WorkoutStep {
  return {
    kind: "work",
    label: null,
    notes: null,
    duration_s: null,
    distance_m: null,
    laps: null,
    power: null,
    cadence: null,
    rpe: null,
    event_key: null,
    start_type: null,
    target_time_ms: null,
    gear: null,
    ...over,
  };
}

const steps: WorkoutItem[] = [
  step({ kind: "warmup", duration_s: 600, power: { unit: "ftp_pct", low: 50, high: 65 } }),
  {
    type: "repeat",
    count: 3,
    steps: [
      {
        type: "repeat",
        count: 4,
        steps: [
          step({ label: "Flying", event_key: "f200", start_type: "flying", gear: { chainring_teeth: 50, cog_teeth: 15 } }),
          step({ kind: "recovery", laps: 3, rpe: 2 }),
        ],
      },
      step({ kind: "recovery", duration_s: 600, notes: "  spin  " }),
    ],
  },
  step({ event_key: "500m", start_type: "standing", target_time_ms: 35_500 }),
  step({ kind: "cooldown", cadence: { low: 85, high: 95 } }),
];

function input(over: Partial<WorkoutCardInput> = {}): WorkoutCardInput {
  return { name: "Sprint sets", date: "Tue, Nov 11", steps, estimate: null, ftpW: 280, bests: { "f200|flying": 11_420 }, ...over };
}

describe("powerText", () => {
  it("is watts from the FTP, else % FTP; watt targets stay as written", () => {
    const pct = step({ power: { unit: "ftp_pct", low: 90, high: 95 } });
    expect(powerText(pct, 280, texts, fmt)).toBe("252–266 W");
    expect(powerText(pct, null, texts, fmt)).toBe("90–95 % FTP");
    expect(powerText(step({ power: { unit: "watts", low: 300, high: 300 } }), null, texts, fmt)).toBe("300 W");
    expect(powerText(step({}), 280, texts, fmt)).toBeNull();
  });
});

describe("bestTimes", () => {
  it("keeps the fastest per event and start, whatever the track", () => {
    expect(
      bestTimes([
        { event_key: "f200", start_type: "flying", time_ms: 11_600 },
        { event_key: "f200", start_type: "flying", time_ms: 11_420 },
        { event_key: "500m", start_type: "standing", time_ms: 36_000 },
      ]),
    ).toEqual({ "f200|flying": 11_420, "500m|standing": 36_000 });
  });
});

describe("workoutCardModel", () => {
  it("keeps the tree as written, a line per repeat, with watts, times and gear", () => {
    const model = workoutCardModel(input({ estimate: { duration_s: 3900, tss: 61.6, unrated_s: 0, open_steps: 0, segments: [] } }), texts, fmt);
    expect(model.subtitle).toBe("Tue, Nov 11 · 1 h 05 · 62 TSS");
    expect(model.footer).toBe("Watts at FTP 280 W");
    const rows = model.rows.map((row) => [row.depth, row.length, row.label, row.detail]);
    expect(rows).toEqual([
      [0, "10:00", "Warm-up", "140–182 W"],
      [0, null, "3 ×", null],
      [1, null, "4 ×", null],
      [2, "200 m", "Flying", "Flying 200 m · best 11.420 s · 50×15"],
      [2, "3 laps", "Recovery", "RPE 2"],
      [1, "10:00", "Recovery", "spin"],
      [0, "500 m", "500 m · Standing start", "35.500 s"],
      [0, "Lap", "Cool-down", "85–95 rpm"],
    ]);
    expect(model.rows[3].isTrack).toBe(true);
  });

  it("names the athlete's own gear and says when power stays in % FTP", () => {
    const model = workoutCardModel(input({ ftpW: null, bests: {}, gearLabels: { "50×15": "Track · 50×15" } }), texts, fmt);
    expect(model.rows[3].detail).toBe("Flying 200 m · Track 50×15");
    expect(model.rows[0].detail).toBe("50–65 % FTP");
    expect(model.footer).toBe("Power in % FTP");
    expect(model.subtitle).toBe("Tue, Nov 11");
  });

  it("has no footer without % FTP targets", () => {
    expect(workoutCardModel(input({ steps: [step({ duration_s: 60, rpe: 5 })] }), texts, fmt).footer).toBeNull();
  });
});

describe("fitRows", () => {
  const row = (detail: string | null): WorkoutCardRow => ({ depth: 0, kind: "work", isTrack: false, length: "1:00", label: "Effort", detail });

  it("keeps full size when it fits, shrinks, then drops details, then cuts", () => {
    const rows = Array.from({ length: 10 }, () => row("250 W"));
    // A row with detail is 2.5 × rowPx at full size.
    expect(fitRows(rows, 1000, 40)).toEqual({ scale: 1, withDetail: true, shown: 10 });
    const smaller = fitRows(rows, 700, 40);
    expect(smaller).toMatchObject({ withDetail: true, shown: 10 });
    expect(smaller.scale).toBeGreaterThan(0.6);
    expect(smaller.scale * 1000).toBeLessThanOrEqual(700);
    const bare = fitRows(rows, 400, 40);
    expect(bare.withDetail).toBe(false);
    expect(bare.shown).toBe(10);
    const cut = fitRows(rows, 200, 40);
    expect(cut).toMatchObject({ scale: 0.55, withDetail: false });
    expect(cut.shown).toBeLessThan(10);
    expect((cut.shown + 1) * 40 * 0.55 * 1.45).toBeLessThanOrEqual(200);
  });

  it("grows up to the max scale and counts wrapped detail lines", () => {
    const rows = [row("250 W"), row("a long note")];
    expect(fitRows(rows, 1000, 40, () => 1, 1.5).scale).toBe(1.5);
    // Three detail lines each: 2 × 40 × (1.45 + 3 × 1.05) ≈ 368 at scale 1.
    expect(fitRows(rows, 370, 40, () => 3, 1.5)).toMatchObject({ scale: 1, withDetail: true });
  });
});

describe("clipText and file names", () => {
  const ctx = { measureText: (text: string) => ({ width: text.length * 10 }) } as unknown as CanvasRenderingContext2D;

  it("cuts with an ellipsis to the width", () => {
    expect(clipText(ctx, "short", 100)).toBe("short");
    expect(clipText(ctx, "a much longer line", 100)).toBe("a much lo…");
  });

  it("wraps words over lines, the last one cut", () => {
    // 10 px a character: 10 characters a line.
    expect(wrapText(ctx, "250 W · 95 rpm · 50×15", 100, 3)).toEqual(["250 W", "95 rpm", "50×15"]);
    expect(wrapText(ctx, "250 W · 95 rpm · 50×15", 100, 2)).toEqual(["250 W", "95 rpm ·…"]);
    // A part longer than a line breaks between its words.
    expect(wrapText(ctx, "250 W · spin easy and drink", 100, 3)).toEqual(["250 W", "spin easy", "and drink"]);
    expect(wrapText(ctx, "short", 100, 3)).toEqual(["short"]);
  });

  it("slugs the name and the size", () => {
    expect(workoutCardFileName("Départs arrêtés 3×500", "stem")).toBe("apex-departs-arretes-3-500-stem.png");
    expect(workoutCardFileName("!!", "phone")).toBe("apex-workout-phone.png");
  });
});

describe("drawWorkoutCard", () => {
  function fakeContext() {
    const drawn: { text: string; y: number }[] = [];
    const state: Record<string, unknown> = {};
    const ctx = new Proxy(state, {
      get(target, prop: string) {
        if (prop === "fillText") return (text: string, _x: number, y: number) => drawn.push({ text, y });
        if (prop === "measureText") return (text: string) => ({ width: text.length * 10 });
        if (prop in target) return target[prop];
        return vi.fn();
      },
      set(target, prop: string, value) {
        target[prop] = value;
        return true;
      },
    });
    return { ctx: ctx as unknown as CanvasRenderingContext2D, drawn };
  }

  it("draws every step inside the lock screen's free area", () => {
    const model = workoutCardModel(input(), texts, fmt);
    const { ctx, drawn } = fakeContext();
    drawWorkoutCard(ctx, model, "phone", (n) => `+ ${n} more`);
    const textsDrawn = drawn.map((d) => d.text);
    expect(textsDrawn).toContain("APEXCYCLING");
    expect(textsDrawn).toContain("Sprint sets");
    expect(textsDrawn).toContain("3 ×");
    expect(textsDrawn).toContain("Watts at FTP 280 W");
    expect(textsDrawn.some((text) => text.startsWith("+ "))).toBe(false);
    const layout = CARD_LAYOUTS.phone;
    for (const { y } of drawn) {
      expect(y).toBeGreaterThan(layout.top);
      expect(y).toBeLessThanOrEqual(layout.bottom);
    }
  });

  it("says how many steps didn't fit on a long workout", () => {
    const long = Array.from({ length: 80 }, (_, i) => step({ duration_s: 60, label: `Step ${i}`, power: { unit: "watts", low: 200, high: null } }));
    const { ctx, drawn } = fakeContext();
    drawWorkoutCard(ctx, workoutCardModel(input({ steps: long }), texts, fmt), "stem", (n) => `+ ${n} more`);
    expect(drawn.some((d) => /^\+ \d+ more$/.test(d.text))).toBe(true);
    expect(Math.max(...drawn.map((d) => d.y))).toBeLessThanOrEqual(CARD_LAYOUTS.stem.bottom);
  });
});
