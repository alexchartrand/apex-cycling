import { describe, expect, it } from "vitest";
import { createFormatters } from "../../i18n/format";
import type { WorkoutItem } from "./types";
import {
  appendNode,
  canHoldRepeat,
  draftErrors,
  draftFrom,
  draftPayload,
  draftSteps,
  duplicateNode,
  durationToInput,
  emptyDraft,
  moveNode,
  newRepeat,
  newStep,
  parseDuration,
  parseTags,
  removeNode,
  withEvent,
  type DraftRepeat,
  type DraftStep,
  type WorkoutDraft,
} from "./workoutDraft";

const en = createFormatters("en");
const fr = createFormatters("fr");

const step = (overrides: Partial<Extract<WorkoutItem, { kind: unknown }>> = {}) => ({
  kind: "work" as const,
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
  ...overrides,
});

const sample: WorkoutItem[] = [
  step({ kind: "warmup", label: "Warm-up", duration_s: 1200, rpe: 3, notes: "Easy laps" }),
  {
    type: "repeat",
    count: 3,
    steps: [
      {
        type: "repeat",
        count: 4,
        steps: [
          step({ label: "Flying 200", event_key: "f200", start_type: "flying", laps: 3, target_time_ms: 11_200, gear: { chainring_teeth: 50, cog_teeth: 15 } }),
          step({ kind: "recovery", laps: 3, rpe: 2 }),
        ],
      },
      step({ kind: "recovery", duration_s: 600, power: { unit: "ftp_pct", low: 45, high: 55 } }),
    ],
  },
  step({ kind: "cooldown", distance_m: 2500.5, cadence: { low: 90, high: null }, power: { unit: "watts", low: 150, high: null } }),
  step({ label: "Open", rpe: 5 }),
];

const draftOf = (steps: WorkoutItem[], fmt = en): WorkoutDraft => draftFrom({ name: "Test", description: null, tags: ["track"], steps }, fmt);

describe("durations", () => {
  it.each([
    ["45", 45],
    ["5:00", 300],
    ["1:30", 90],
    ["1:00:00", 3600],
    [" 10:05 ", 605],
  ])("%s → %s s", (text, seconds) => {
    expect(parseDuration(text)).toBe(seconds);
  });

  it.each(["", "0", "1:75", "abc", "1:2:3:4", "-5"])("refuses %j", (text) => {
    expect(parseDuration(text)).toBeNull();
  });

  it("writes back what parses again", () => {
    for (const seconds of [8, 59, 60, 90, 1200, 3600, 5405]) expect(parseDuration(durationToInput(seconds))).toBe(seconds);
    expect(durationToInput(3725)).toBe("1:02:05");
  });
});

describe("draft ⇄ payload", () => {
  it("round-trips a nested workout unchanged", () => {
    expect(draftPayload(draftOf(sample))?.steps).toEqual(sample);
  });

  it("reads French decimals back", () => {
    const draft = draftOf(sample, fr);
    const cooldown = draft.steps[2] as DraftStep;
    expect(cooldown.distance).toBe("2500,5");
    const flying = ((draft.steps[1] as DraftRepeat).steps[0] as DraftRepeat).steps[0] as DraftStep;
    expect(flying.targetTime).toBe("11,200");
    expect(draftPayload(draft)?.steps).toEqual(sample);
  });

  it("trims the name and cleans the tags", () => {
    const payload = draftPayload({ ...draftOf(sample), name: "  Sprint day ", tags: "Sprint, track,, sprint ", description: "  " });
    expect(payload).toMatchObject({ name: "Sprint day", tags: ["sprint", "track"], description: null });
    expect(parseTags("")).toEqual([]);
  });

  it("the starting draft is valid", () => {
    expect(draftPayload({ ...emptyDraft(), name: "x" })).not.toBeNull();
  });
});

describe("validation", () => {
  const withStep = (patch: Partial<DraftStep>): WorkoutDraft => ({ name: "x", description: "", tags: "", steps: [{ ...newStep(), ...patch }] });
  const errorsOf = (draft: WorkoutDraft) => Object.values(draftErrors(draft).nodes).flat();

  it.each<[Partial<DraftStep>, string]>([
    [{ duration: "0" }, "duration"],
    [{ duration: "7:00:00" }, "duration"],
    [{ lengthMode: "distance", distance: "" }, "distance"],
    [{ lengthMode: "laps", laps: "2.5" }, "laps"],
    [{ powerUnit: "ftp_pct", powerLow: "" }, "powerLow"],
    [{ powerUnit: "ftp_pct", powerLow: "350" }, "powerLow"],
    [{ powerUnit: "watts", powerLow: "300", powerHigh: "250" }, "powerHigh"],
    [{ cadenceHigh: "100" }, "cadenceLow"],
    [{ cadenceLow: "100", cadenceHigh: "90" }, "cadenceHigh"],
    [{ targetTime: "11.2" }, "targetTime"],
    [{ eventKey: "f200", targetTime: "fast" }, "targetTime"],
    [{ chainring: "50" }, "gear"],
    [{ chainring: "50", cog: "70" }, "gear"],
  ])("%j → %s", (patch, field) => {
    expect(errorsOf(withStep(patch))).toEqual([field]);
  });

  it("an open step and a lone watt value are fine", () => {
    expect(errorsOf(withStep({ lengthMode: "open", powerUnit: "watts", powerLow: "400" }))).toEqual([]);
  });

  it("flags a repeat's count and an empty repeat", () => {
    const repeat: DraftRepeat = { ...newRepeat(), count: "1", steps: [] };
    const errors = draftErrors({ name: "x", description: "", tags: "", steps: [repeat] });
    expect(errors.nodes[repeat.id]).toEqual(["count", "empty"]);
    expect(draftSteps({ name: "", description: "", tags: "", steps: [repeat] })).toBeNull();
  });

  it("the chart doesn't wait for a name, the save does", () => {
    const draft = { ...emptyDraft(), name: " " };
    expect(draftErrors(draft).name).toBe(true);
    expect(draftSteps(draft)).not.toBeNull();
    expect(draftPayload(draft)).toBeNull();
  });

  it("refuses an empty workout and more than a head unit takes", () => {
    expect(draftErrors({ name: "x", description: "", tags: "", steps: [] }).steps).toBe("empty");
    const many = Array.from({ length: 6 }, () => ({ ...newRepeat(), steps: Array.from({ length: 20 }, () => newStep()) }));
    expect(draftErrors({ name: "x", description: "", tags: "", steps: many }).steps).toBe("tooMany");
  });

  it("too many or too long tags", () => {
    expect(draftErrors({ ...emptyDraft(), name: "x", tags: Array.from({ length: 11 }, (_, i) => `t${i}`).join(",") }).tags).toBe(true);
    expect(draftErrors({ ...emptyDraft(), name: "x", tags: "a".repeat(31) }).tags).toBe(true);
  });

  it("changing the event keeps a start it allows and clears the rest without one", () => {
    const standing = { ...newStep(), eventKey: "1km", startType: "standing", targetTime: "1:05" } as DraftStep;
    expect(withEvent(standing, "500m")).toMatchObject({ startType: "standing", targetTime: "1:05" });
    expect(withEvent(standing, "f200")).toMatchObject({ startType: "" });
    expect(withEvent(standing, "")).toMatchObject({ eventKey: "", startType: "", targetTime: "" });
  });
});

describe("tree operations", () => {
  const a = newStep("warmup");
  const inner = newRepeat();
  const outer: DraftRepeat = { ...newRepeat(), steps: [inner] };
  const b = newStep("cooldown");
  const tree = [a, outer, b];
  const ids = (nodes: { id: string }[]) => nodes.map((node) => node.id);

  it("moves within its own list and stops at the ends", () => {
    expect(ids(moveNode(tree, b.id, -1))).toEqual([a.id, b.id, outer.id]);
    expect(moveNode(tree, a.id, -1)).toEqual(tree);
    const innerFirst = inner.steps[0].id;
    const moved = moveNode(tree, innerFirst, 1);
    expect(ids(((moved[1] as DraftRepeat).steps[0] as DraftRepeat).steps)).toEqual([inner.steps[1].id, innerFirst]);
  });

  it("removes and duplicates nested nodes with fresh ids", () => {
    const removed = removeNode(tree, inner.steps[0].id);
    expect(((removed[1] as DraftRepeat).steps[0] as DraftRepeat).steps).toHaveLength(1);
    const copied = duplicateNode(tree, outer.id);
    expect(copied).toHaveLength(4);
    const copy = copied[2] as DraftRepeat;
    expect(copy.id).not.toBe(outer.id);
    expect((copy.steps[0] as DraftRepeat).steps[0].id).not.toBe(inner.steps[0].id);
  });

  it("appends at the top or into a repeat", () => {
    const step = newStep();
    expect(appendNode(tree, null, step).at(-1)).toBe(step);
    expect((appendNode(tree, inner.id, step)[1] as DraftRepeat).steps[0]).toMatchObject({ steps: [...inner.steps, step] });
  });

  it("nests repeats one level only", () => {
    expect(canHoldRepeat(tree, null)).toBe(true);
    expect(canHoldRepeat(tree, outer.id)).toBe(true);
    expect(canHoldRepeat(tree, inner.id)).toBe(false);
  });
});
