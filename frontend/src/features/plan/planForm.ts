import type { Formatters } from "../../i18n/format";
import { parseTimeInput, timeToInput } from "../records/timeInput";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import type { PlannedEffort, PlannedSession, PlannedSessionWrite, PlanStatus } from "./types";

export type EffortRow = {
  label: string;
  reps: string;
  /** "" = no event (a free-form block like "tempo"). */
  eventKey: "" | StandardEventKey;
  startType: "" | "standing" | "flying";
  time: string;
  /** "" = no gear asked for. */
  gearId: string;
};

export type PlanForm = {
  date: string;
  title: string;
  description: string;
  targets: EffortRow[];
};

export type PlanFormErrors = { title?: true; date?: true; targets: Record<number, "label" | "reps" | "time"> };

export const emptyEffortRow = (): EffortRow => ({ label: "", reps: "1", eventKey: "", startType: "", time: "", gearId: "" });

export function emptyPlanForm(date: string): PlanForm {
  return { date, title: "", description: "", targets: [] };
}

export function planFormFrom(plan: PlannedSession, fmt: Pick<Formatters, "seconds" | "lapTime">): PlanForm {
  return {
    date: plan.planned_date,
    title: plan.title,
    description: plan.description ?? "",
    targets: plan.targets.map((target) => ({
      label: target.label,
      reps: String(target.reps),
      eventKey: (STANDARD_EVENT_KEYS as readonly string[]).includes(target.event_key ?? "") ? (target.event_key as StandardEventKey) : "",
      startType: target.start_type ?? "",
      time: target.target_time_ms != null ? timeToInput(target.target_time_ms, fmt) : "",
      gearId: target.gear_setup_id ?? "",
    })),
  };
}

/** Changing a block's event keeps its start when the event has it, and clears the start and time when the event goes. */
export function withRowEvent(row: EffortRow, eventKey: "" | StandardEventKey): EffortRow {
  if (eventKey === "") return { ...row, eventKey, startType: "", time: "" };
  const allowed = EVENT_START_TYPES[eventKey];
  return { ...row, eventKey, startType: row.startType && allowed.includes(row.startType) ? row.startType : "" };
}

export function planFormErrors(form: PlanForm): PlanFormErrors {
  const errors: PlanFormErrors = { targets: {} };
  if (form.title.trim() === "") errors.title = true;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.date)) errors.date = true;
  form.targets.forEach((row, index) => {
    const reps = Number(row.reps);
    if (row.label.trim() === "") errors.targets[index] = "label";
    else if (!Number.isInteger(reps) || reps < 1 || reps > 99) errors.targets[index] = "reps";
    else if (row.time.trim() !== "" && (row.eventKey === "" || parseTimeInput(row.time) == null)) errors.targets[index] = "time";
  });
  return errors;
}

export function hasPlanErrors(errors: PlanFormErrors): boolean {
  return errors.title === true || errors.date === true || Object.keys(errors.targets).length > 0;
}

export function planPayload(form: PlanForm): PlannedSessionWrite | null {
  if (hasPlanErrors(planFormErrors(form))) return null;
  return {
    planned_date: form.date,
    title: form.title.trim(),
    description: form.description.trim() || null,
    targets: form.targets.map(
      (row): PlannedEffort => ({
        label: row.label.trim(),
        reps: Number(row.reps),
        event_key: row.eventKey || null,
        start_type: row.eventKey ? row.startType || null : null,
        target_time_ms: row.eventKey && row.time.trim() !== "" ? parseTimeInput(row.time) : null,
        gear_setup_id: row.gearId || null,
      }),
    ),
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
