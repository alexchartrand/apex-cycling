import type { Formatters } from "../../i18n/format";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import { parseTimeInput, timeToInput } from "../records/timeInput";
import type { Goal, GoalCreate, GoalUpdate } from "./types";

export type GoalForm = {
  eventKey: StandardEventKey;
  startType: "standing" | "flying";
  time: string;
  date: string;
  /** "" = on any track. */
  trackId: string;
  /** "" = the aero test's bike. */
  bikeId: string;
  notes: string;
};

export type GoalFormErrors = { time?: true; date?: true };

/** A new goal: the kilo from a standing start, on any track, with the date left for the rider to pick. */
export function emptyGoalForm(): GoalForm {
  return { eventKey: "1km", startType: "standing", time: "", date: "", trackId: "", bikeId: "", notes: "" };
}

export function goalFormFrom(goal: Goal, fmt: Pick<Formatters, "seconds" | "lapTime">): GoalForm {
  return {
    eventKey: (STANDARD_EVENT_KEYS as readonly string[]).includes(goal.event_key) ? (goal.event_key as StandardEventKey) : "1km",
    startType: goal.start_type === "flying" ? "flying" : "standing",
    time: timeToInput(goal.target_time_ms, fmt),
    date: goal.target_date,
    trackId: goal.track_id ?? "",
    bikeId: goal.bike_id ?? "",
    notes: goal.notes ?? "",
  };
}

/** Switching event keeps the start type when the new event has it, else falls back to its first. */
export function withEvent(form: GoalForm, eventKey: StandardEventKey): GoalForm {
  const allowed = EVENT_START_TYPES[eventKey];
  return { ...form, eventKey, startType: allowed.includes(form.startType) ? form.startType : allowed[0] };
}

export function goalFormErrors(form: GoalForm): GoalFormErrors {
  const errors: GoalFormErrors = {};
  if (parseTimeInput(form.time) == null) errors.time = true;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.date)) errors.date = true;
  return errors;
}

export function goalCreatePayload(form: GoalForm): GoalCreate | null {
  const errors = goalFormErrors(form);
  if (errors.time || errors.date) return null;
  return {
    event_key: form.eventKey,
    start_type: form.startType,
    target_time_ms: parseTimeInput(form.time)!,
    target_date: form.date,
    track_id: form.trackId || null,
    bike_id: form.bikeId || null,
    notes: form.notes.trim() || null,
  };
}

/** What changed from the saved goal (the event and start can't change). */
export function goalUpdatePayload(form: GoalForm): GoalUpdate | null {
  const created = goalCreatePayload(form);
  if (!created) return null;
  return {
    target_time_ms: created.target_time_ms,
    target_date: created.target_date,
    track_id: created.track_id,
    bike_id: created.bike_id,
    notes: created.notes,
  };
}

/** Whole days to the target date: "in 12 days", today, or past. */
export function dueState(daysLeft: number, achieved: boolean): "reached" | "today" | "overdue" | "upcoming" {
  if (achieved) return "reached";
  if (daysLeft === 0) return "today";
  return daysLeft < 0 ? "overdue" : "upcoming";
}

/** The predicted time against the target: negative = the prediction beats it. */
export function predictedGapMs(goal: Goal): number | null {
  return goal.prediction ? goal.prediction.time_ms - goal.target_time_ms : null;
}
