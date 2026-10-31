import { describe, expect, it } from "vitest";
import type { DraftRepeat, DraftStep } from "../workouts/workoutDraft";
import {
  emptyPlanForm,
  hasPlanErrors,
  linkCandidates,
  outstanding,
  planFormErrors,
  planFormFrom,
  planPayload,
  targetsToSteps,
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
  can_edit: true,
  can_mark: true,
  intervals: null,
  ...over,
});

const fmt = { seconds: () => "", lapTime: () => "1:10.500", language: "en" as const };

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
  it("needs a title and a date; a workout's steps are checked like the editor's", () => {
    expect(planFormErrors(emptyPlanForm(""))).toEqual({ title: true, date: true, nodes: {} });
    const ok = { ...emptyPlanForm("2026-11-10"), title: "Openers" };
    expect(hasPlanErrors(planFormErrors(ok))).toBe(false);
    expect(planFormErrors({ ...ok, steps: [] }).steps).toBe("empty");
    const form = planFormFrom(plan({ workout: STEPS }), fmt);
    const broken = { ...form, steps: [{ ...(form.steps![0] as DraftStep), duration: "soon" }] };
    expect(Object.values(planFormErrors(broken).nodes)).toEqual([["duration"]]);
    expect(planPayload(broken)).toBeNull();
  });

  it("a plan without a workout keeps its older efforts as they were", () => {
    const targets = [{ label: "Kilo", reps: 2, event_key: "1km", start_type: "standing" as const, target_time_ms: 70_500, gear_setup_id: "g1", gear_label: "Track · 50×15" }];
    const form = planFormFrom(plan({ description: "Easy", targets }), fmt);
    expect(form).toMatchObject({ date: "2026-11-10", description: "Easy", steps: null, legacyTargets: targets });
    expect(planPayload({ ...form, title: " Openers ", description: "  " })).toEqual({
      planned_date: "2026-11-10",
      title: "Openers",
      description: null,
      targets: [{ label: "Kilo", reps: 2, event_key: "1km", start_type: "standing", target_time_ms: 70_500, gear_setup_id: "g1" }],
      workout: null,
      source_workout_id: null,
    });
  });

  it("an edit starts from the plan's own copy of the workout and sends it back", () => {
    const form = planFormFrom(plan({ workout: STEPS, source_workout_id: "w1" }), fmt);
    expect(form.steps).toHaveLength(2);
    expect(form.sourceWorkoutId).toBe("w1");
    const payload = planPayload(form)!;
    expect(payload.targets).toEqual([]);
    expect(payload.source_workout_id).toBe("w1");
    expect(payload.workout).toEqual(STEPS.map((item) => ("type" in item ? item : { ...item })));
    // Removing the workout drops its source too.
    expect(planPayload({ ...form, steps: null })).toMatchObject({ workout: null, source_workout_id: null });
  });

  it("a library workout fills a blank title and description, never typed ones", () => {
    const workout = { id: "w2", name: "Sprint openers", description: "Short and sharp", steps: STEPS };
    const filled = withLibraryWorkout({ ...emptyPlanForm("2026-11-10"), legacyTargets: plan().targets }, workout, fmt);
    expect(filled).toMatchObject({ title: "Sprint openers", description: "Short and sharp", sourceWorkoutId: "w2", legacyTargets: [] });
    const kept = withLibraryWorkout({ ...emptyPlanForm("2026-11-10"), title: "Mine", description: "My notes" }, workout, fmt);
    expect(kept).toMatchObject({ title: "Mine", description: "My notes" });
  });

  it("turns older efforts into steps: event distance, repeats for reps, gear as teeth", () => {
    const nodes = targetsToSteps(
      [
        { label: "Kilo", reps: 2, event_key: "1km", start_type: "standing", target_time_ms: 70_500, gear_setup_id: "g1" },
        { label: "Tempo", reps: 1, event_key: null, start_type: null, target_time_ms: null, gear_setup_id: null },
      ],
      [{ id: "g1", chainring_teeth: 50, cog_teeth: 15 }],
      fmt,
    );
    const repeat = nodes[0] as DraftRepeat;
    expect(repeat).toMatchObject({ type: "repeat", count: "2" });
    expect(repeat.steps[0]).toMatchObject({ label: "Kilo", lengthMode: "open", eventKey: "1km", startType: "standing", targetTime: "1:10.500", chainring: "50", cog: "15" });
    expect(nodes[1]).toMatchObject({ type: "step", label: "Tempo", lengthMode: "open", eventKey: "", chainring: "" });
    const payload = planPayload({ ...emptyPlanForm("2026-11-10"), title: "T", steps: nodes })!;
    expect(payload.workout).toHaveLength(2);
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
});
