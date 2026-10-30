import type { Formatters } from "../../i18n/format";
import type { Gear } from "../equipment/types";
import { timeToInput } from "../records/timeInput";
import { STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import { gearKey, type Workout, type WorkoutItem } from "../workouts/types";
import { draftErrors, draftNodes, draftSteps, newRepeat, newStep, type DraftNode, type DraftRepeat, type DraftStep, type StepField, type WorkoutDraft } from "../workouts/workoutDraft";
import type { PlannedEffort, PlannedSession, PlannedSessionWrite, PlanStatus } from "./types";

export type PlanForm = {
  date: string;
  title: string;
  description: string;
  /** An older plan's free-form efforts, kept as they are until turned into steps. */
  legacyTargets: PlannedEffort[];
  /** The workout being planned; null = none. */
  steps: DraftNode[] | null;
  /** The library workout the steps were copied from. */
  sourceWorkoutId: string | null;
};

export type PlanFormErrors = { title?: true; date?: true; steps?: "empty" | "tooMany"; nodes: Record<string, StepField[]> };

type Fmt = Pick<Formatters, "seconds" | "lapTime" | "language">;

const asDraft = (steps: DraftNode[]): WorkoutDraft => ({ name: "", description: "", tags: "", steps });

export function emptyPlanForm(date: string): PlanForm {
  return { date, title: "", description: "", legacyTargets: [], steps: null, sourceWorkoutId: null };
}

export function planFormFrom(plan: PlannedSession, fmt: Fmt): PlanForm {
  return {
    date: plan.planned_date,
    title: plan.title,
    description: plan.description ?? "",
    legacyTargets: plan.workout ? [] : plan.targets,
    steps: plan.workout ? draftNodes(plan.workout, fmt) : null,
    sourceWorkoutId: plan.source_workout_id,
  };
}

/** The form with a library workout's steps; its name and description fill a blank title and description. */
export function withLibraryWorkout(form: PlanForm, workout: Pick<Workout, "id" | "name" | "description" | "steps">, fmt: Fmt): PlanForm {
  return {
    ...form,
    title: form.title.trim() === "" ? workout.name : form.title,
    description: form.description.trim() === "" ? (workout.description ?? "") : form.description,
    legacyTargets: [],
    steps: draftNodes(workout.steps, fmt),
    sourceWorkoutId: workout.id,
  };
}

/**
 * An older plan's efforts as workout steps: each one a work step ending on its
 * event's distance (or the lap button without an event), in a repeat when it
 * has several reps. A saved gear becomes its teeth.
 */
export function targetsToSteps(targets: PlannedEffort[], gears: Pick<Gear, "id" | "chainring_teeth" | "cog_teeth">[], fmt: Fmt): DraftNode[] {
  return targets.map((target) => {
    const gear = gears.find((g) => g.id === target.gear_setup_id);
    const step: DraftStep = {
      ...newStep("work", ""),
      label: target.label,
      lengthMode: "open",
      eventKey: (STANDARD_EVENT_KEYS as readonly string[]).includes(target.event_key ?? "") ? (target.event_key as StandardEventKey) : "",
      startType: target.event_key ? (target.start_type ?? "") : "",
      targetTime: target.event_key && target.target_time_ms != null ? timeToInput(target.target_time_ms, fmt) : "",
      chainring: gear ? String(gear.chainring_teeth) : "",
      cog: gear ? String(gear.cog_teeth) : "",
    };
    if (target.reps < 2) return step;
    const block: DraftRepeat = { ...newRepeat(), count: String(target.reps), steps: [step] };
    return block;
  });
}

/** The plan's matched gears by `gearKey`, for `WorkoutSteps`. */
export function workoutGearLabels(plan: Pick<PlannedSession, "workout_gears">): Record<string, string> {
  return Object.fromEntries(plan.workout_gears.map((gear) => [gearKey(gear.chainring_teeth, gear.cog_teeth), gear.label]));
}

export function planFormErrors(form: PlanForm): PlanFormErrors {
  const errors: PlanFormErrors = { nodes: {} };
  if (form.title.trim() === "") errors.title = true;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.date)) errors.date = true;
  if (form.steps != null) {
    const workout = draftErrors(asDraft(form.steps));
    if (workout.steps) errors.steps = workout.steps;
    errors.nodes = workout.nodes;
  }
  return errors;
}

export function hasPlanErrors(errors: PlanFormErrors): boolean {
  return errors.title === true || errors.date === true || errors.steps != null || Object.keys(errors.nodes).length > 0;
}

/** The steps as the estimate takes them; null while there are none or they'd be refused. */
export function planSteps(form: PlanForm): WorkoutItem[] | null {
  return form.steps == null ? null : draftSteps(asDraft(form.steps));
}

export function planPayload(form: PlanForm): PlannedSessionWrite | null {
  if (hasPlanErrors(planFormErrors(form))) return null;
  const workout = planSteps(form);
  return {
    planned_date: form.date,
    title: form.title.trim(),
    description: form.description.trim() || null,
    // The server sends gear labels back; it doesn't take them.
    targets: workout ? [] : form.legacyTargets.map(({ gear_label: _label, ...target }) => target),
    workout,
    source_workout_id: workout ? form.sourceWorkoutId : null,
  };
}

/** Plans still waiting for an answer, soonest first, from `from` (a day) on, plus the overdue ones back to `since`. */
export function outstanding(plans: PlannedSession[], since: string): PlannedSession[] {
  return plans.filter((plan) => plan.status === "planned" && plan.planned_date >= since).sort((a, b) => a.planned_date.localeCompare(b.planned_date));
}

/** Sessions ridden within `days` of the plan's date, nearest first: the ones it can be linked to. */
export function linkCandidates<T extends { event_date: string }>(plan: PlannedSession, sessions: T[], days = 2): T[] {
  const target = Date.parse(`${plan.planned_date}T00:00:00Z`);
  const distance = (session: T) => Math.abs(Date.parse(`${session.event_date}T00:00:00Z`) - target) / 86_400_000;
  return sessions.filter((session) => distance(session) <= days).sort((a, b) => distance(a) - distance(b));
}

export const STATUS_TONE: Record<PlanStatus, "neutral" | "positive" | "marker"> = { planned: "neutral", done: "positive", skipped: "marker" };

/** "3 × Standing start — 500 m, 34.000, Track bike · 50×15" */
export function effortText(
  target: PlannedEffort,
  words: { reps: (n: number, label: string) => string; event: (key: StandardEventKey) => string; time: (ms: number) => string },
): string {
  const head = target.reps > 1 ? words.reps(target.reps, target.label) : target.label;
  const parts = [
    target.event_key ? words.event(target.event_key as StandardEventKey) : null,
    target.target_time_ms != null ? words.time(target.target_time_ms) : null,
    target.gear_label ?? null,
  ].filter(Boolean);
  return parts.length > 0 ? `${head} — ${parts.join(", ")}` : head;
}
