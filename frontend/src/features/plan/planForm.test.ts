import { describe, expect, it } from "vitest";
import {
  emptyPlanForm,
  hasPlanErrors,
  hasRecordingTargets,
  linkCandidates,
  linkChoices,
  outstanding,
  planFormErrors,
  planFormFrom,
  planPayload,
  withLibraryWorkout,
  workoutGearLabels,
} from "./planForm";
import type { PlannedSession } from "./types";

const plan = (over: Partial<PlannedSession> = {}): PlannedSession => ({
  id: "p",
  planned_date: "2026-11-10",
  title: "Kilo openers",
  description: null,
  targets: [],
  workout: null,
  workout_estimate: null,
  workout_gears: [],
  source_workout_id: null,
  status: "planned",
  created_by_name: null,
  session: null,
  activity: null,
  can_edit: true,
  can_mark: true,
  intervals: null,
  ...over,
});

const STEPS = [
  { kind: "warmup" as const, label: null, notes: null, duration_s: 600, distance_m: null, laps: null, power: null, cadence: null, rpe: 3, event_key: null, start_type: null, target_time_ms: null, gear: null },
  {
    type: "repeat" as const,
    count: 3,
    steps: [
      { kind: "work" as const, label: "Flying", notes: null, duration_s: null, distance_m: null, laps: null, power: null, cadence: null, rpe: null, event_key: "f200" as const, start_type: "flying" as const, target_time_ms: null, gear: { chainring_teeth: 50, cog_teeth: 15 } },
    ],
  },
];

describe("plan form", () => {
  it("needs a title, a date and a workout", () => {
    expect(planFormErrors(emptyPlanForm(""))).toEqual({ title: true, date: true, workout: true });
    const untitled = { ...emptyPlanForm("2026-11-10"), title: "Openers" };
    expect(planPayload(untitled)).toBeNull();
    const ok = { ...untitled, workout: STEPS, sourceWorkoutId: "w1" };
    expect(hasPlanErrors(planFormErrors(ok))).toBe(false);
  });

  it("a plan without a workout keeps its older efforts as they were", () => {
    const targets = [{ label: "Kilo", reps: 2, event_key: "1km", start_type: "standing" as const, target_time_ms: 70_500, gear_setup_id: "g1", gear_label: "Track · 50×15" }];
    const form = planFormFrom(plan({ description: "Easy", targets }));
    expect(form).toMatchObject({ date: "2026-11-10", description: "Easy", workout: null, legacyTargets: targets });
    expect(planPayload({ ...form, title: " Openers ", description: "  " })).toEqual({
      planned_date: "2026-11-10",
      title: "Openers",
      description: null,
      targets: [{ label: "Kilo", reps: 2, event_key: "1km", start_type: "standing", target_time_ms: 70_500, gear_setup_id: "g1" }],
      workout: null,
      source_workout_id: null,
    });
  });

  it("an edit keeps the plan's own copy of the workout and sends it back unchanged", () => {
    const form = planFormFrom(plan({ workout: STEPS, source_workout_id: "w1" }));
    const payload = planPayload(form)!;
    expect(payload).toMatchObject({ targets: [], workout: STEPS, source_workout_id: "w1" });
  });

  it("a library workout replaces the steps and older efforts, and fills a blank title and description, never typed ones", () => {
    const workout = { id: "w2", name: "Sprint openers", description: "Short and sharp", steps: STEPS };
    const filled = withLibraryWorkout({ ...emptyPlanForm("2026-11-10"), legacyTargets: plan().targets }, workout);
    expect(filled).toMatchObject({ title: "Sprint openers", description: "Short and sharp", sourceWorkoutId: "w2", legacyTargets: [], workout: STEPS });
    const kept = withLibraryWorkout({ ...emptyPlanForm("2026-11-10"), title: "Mine", description: "My notes" }, workout);
    expect(kept).toMatchObject({ title: "Mine", description: "My notes" });
  });

  it("names a workout's gears the athlete's way", () => {
    const labels = workoutGearLabels(plan({ workout_gears: [{ chainring_teeth: 50, cog_teeth: 15, gear_setup_id: "g1", label: "Track bike · 50×15" }] }));
    expect(labels).toEqual({ "50×15": "Track bike · 50×15" });
  });
});

describe("plan lists", () => {
  it("keeps the unanswered plans from the cut-off date, soonest first", () => {
    const plans = [
      plan({ id: "later", planned_date: "2026-11-20" }),
      plan({ id: "old", planned_date: "2026-10-01" }),
      plan({ id: "done", planned_date: "2026-11-11", status: "done" }),
      plan({ id: "soon", planned_date: "2026-11-05" }),
    ];
    expect(outstanding(plans, "2026-11-01").map((p) => p.id)).toEqual(["soon", "later"]);
  });

  it("offers the sessions near the date, nearest first", () => {
    const sessions = [{ event_date: "2026-11-13" }, { event_date: "2026-11-09" }, { event_date: "2026-11-10" }, { event_date: "2026-11-12" }];
    expect(linkCandidates(plan(), sessions).map((s) => s.event_date)).toEqual(["2026-11-10", "2026-11-09", "2026-11-12"]);
    expect(linkCandidates(plan(), sessions, 0).map((s) => s.event_date)).toEqual(["2026-11-10"]);
  });

  it("offers the recordings that aren't part of a session alongside the sessions", () => {
    const sessions = [{ external_event_id: "evt1", event_name: "Track night", event_date: "2026-11-11" }];
    const activities = [
      { id: "a1", name: "Trainer", start_time: "2026-11-10T12:00:00Z", external_event_id: null },
      { id: "a2", name: "Head unit at the track", start_time: "2026-11-11T12:00:00Z", external_event_id: "evt1" },
      { id: "a3", name: "Long ago", start_time: "2026-10-01T12:00:00Z", external_event_id: null },
    ];
    expect(linkChoices(plan(), sessions, activities).map((c) => [c.value, c.kind, c.id, c.event_date])).toEqual([
      ["activity:a1", "activity", "a1", "2026-11-10"],
      ["session:evt1", "session", "evt1", "2026-11-11"],
    ]);
  });
});

describe("hasRecordingTargets", () => {
  const step = { kind: "work" as const, label: null, notes: null, duration_s: 60, distance_m: null, laps: null, power: null, cadence: null, rpe: null, event_key: null, start_type: null, target_time_ms: null, gear: null };
  it("looks for a power or cadence target, inside repeats too", () => {
    expect(hasRecordingTargets([step, { ...step, rpe: 7 }])).toBe(false);
    expect(hasRecordingTargets([{ type: "repeat", count: 3, steps: [{ type: "repeat", count: 2, steps: [{ ...step, cadence: { low: 100, high: null } }] }] }])).toBe(true);
    expect(hasRecordingTargets([{ ...step, power: { unit: "watts", low: 200, high: null } }])).toBe(true);
  });
});
