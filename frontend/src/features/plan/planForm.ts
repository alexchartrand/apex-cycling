import { localIsoDate } from "../../i18n/format";
import type { StandardEventKey } from "../records/types";
import { gearKey, isRepeat, type InnerRepeat, type Workout, type WorkoutItem } from "../workouts/types";
import type { PlannedEffort, PlannedSession, PlannedSessionWrite, PlanStatus } from "./types";

export type PlanForm = {
  date: string;
  title: string;
  description: string;
  /** An older plan's free-form efforts, kept as they are until a workout replaces them. */
  legacyTargets: PlannedEffort[];
  /** The workout's steps as the library (or the plan, when editing) has them; null = none chosen yet. */
  workout: WorkoutItem[] | null;
  /** The library workout the steps were copied from. */
  sourceWorkoutId: string | null;
};

export type PlanFormErrors = { title?: true; date?: true; workout?: true };

export function emptyPlanForm(date: string): PlanForm {
  return { date, title: "", description: "", legacyTargets: [], workout: null, sourceWorkoutId: null };
}

export function planFormFrom(plan: PlannedSession): PlanForm {
  return {
    date: plan.planned_date,
    title: plan.title,
    description: plan.description ?? "",
    legacyTargets: plan.workout ? [] : plan.targets,
    workout: plan.workout,
    sourceWorkoutId: plan.source_workout_id,
  };
}

/** The form with a library workout's steps; its name and description fill a blank title and description. */
export function withLibraryWorkout(form: PlanForm, workout: Pick<Workout, "id" | "name" | "description" | "steps">): PlanForm {
  return {
    ...form,
    title: form.title.trim() === "" ? workout.name : form.title,
    description: form.description.trim() === "" ? (workout.description ?? "") : form.description,
    legacyTargets: [],
    workout: workout.steps,
    sourceWorkoutId: workout.id,
  };
}

/** The plan's matched gears by `gearKey`, for `WorkoutSteps`. */
export function workoutGearLabels(plan: Pick<PlannedSession, "workout_gears">): Record<string, string> {
  return Object.fromEntries(plan.workout_gears.map((gear) => [gearKey(gear.chainring_teeth, gear.cog_teeth), gear.label]));
}

/** A title, a date and a workout from the library (an older plan's efforts stand in until one is chosen). */
export function planFormErrors(form: PlanForm): PlanFormErrors {
  const errors: PlanFormErrors = {};
  if (form.title.trim() === "") errors.title = true;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.date)) errors.date = true;
  if (form.workout == null && form.legacyTargets.length === 0) errors.workout = true;
  return errors;
}

export function hasPlanErrors(errors: PlanFormErrors): boolean {
  return errors.title === true || errors.date === true || errors.workout === true;
}

export function planPayload(form: PlanForm): PlannedSessionWrite | null {
  if (hasPlanErrors(planFormErrors(form))) return null;
  const workout = form.workout;
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

/** Something ridden the plan can be linked to: a sqorz session, or a recording that isn't part of one
 * (a recording linked to a session is reached through it). `value` is unique across both. */
export type LinkChoice = { value: string; kind: "session" | "activity"; id: string; name: string | null; event_date: string };

export function linkChoices(
  plan: PlannedSession,
  sessions: { external_event_id: string; event_name: string; event_date: string }[],
  activities: { id: string; name: string | null; start_time: string; external_event_id: string | null }[],
  days = 2,
): LinkChoice[] {
  const choices: LinkChoice[] = [
    ...sessions.map((s) => ({ value: `session:${s.external_event_id}`, kind: "session" as const, id: s.external_event_id, name: s.event_name, event_date: s.event_date })),
    ...activities
      .filter((a) => a.external_event_id == null)
      .map((a) => ({ value: `activity:${a.id}`, kind: "activity" as const, id: a.id, name: a.name, event_date: localIsoDate(new Date(a.start_time)) })),
  ];
  return linkCandidates(plan, choices, days);
}

/** The workout has a power or cadence target, which a recording answers. */
export function hasRecordingTargets(items: (WorkoutItem | InnerRepeat)[]): boolean {
  return items.some((item) => (isRepeat(item) ? hasRecordingTargets(item.steps) : item.power != null || item.cadence != null));
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
