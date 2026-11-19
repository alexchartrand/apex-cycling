import { addDays, daysBetween, phaseProblem } from "./phases";
import type { Phase, PhaseKind, Sport, TrainingPlan, TrainingPlanWrite } from "./types";

/** The builder's model: raw typed text, turned into a payload only when it holds together. */
export interface PhaseDraft {
  kind: PhaseKind;
  name: string;
  start: string;
  end: string;
  focus: string;
  hours: string;
}

export interface PlanDraft {
  name: string;
  sport: Sport;
  start: string;
  end: string;
  goalText: string;
  goalDate: string;
  hours: string;
  /** "" = none. */
  raceId: string;
  goalId: string;
  phases: PhaseDraft[];
}

export type PlanDraftErrors = {
  name?: true;
  dates?: true;
  goalDate?: true;
  phases?: "phaseOrder" | "phaseOutside" | "phaseOverlap";
};

/** The backend's limit: a plan lasts a year at most (53 weeks). */
export const MAX_PLAN_DAYS = 53 * 7;
export const DEFAULT_WEEKS = 12;

function nextMonday(today: string): string {
  const weekday = (new Date(`${today}T00:00:00Z`).getUTCDay() + 6) % 7;
  return weekday === 0 ? today : addDays(today, 7 - weekday);
}

export function emptyDraft(today: string, sport: Sport = "cycling"): PlanDraft {
  const start = nextMonday(today);
  return {
    name: "",
    sport,
    start,
    end: addDays(start, DEFAULT_WEEKS * 7 - 1),
    goalText: "",
    goalDate: "",
    hours: "",
    raceId: "",
    goalId: "",
    phases: [],
  };
}

const text = (value: number | null | undefined) => (value == null ? "" : String(value));

export function phaseDraft(phase: Phase): PhaseDraft {
  return {
    kind: phase.kind,
    name: phase.name ?? "",
    start: phase.start,
    end: phase.end,
    focus: phase.focus ?? "",
    hours: text(phase.hours),
  };
}

export function draftFrom(plan: TrainingPlan): PlanDraft {
  return {
    name: plan.name,
    sport: plan.sport,
    start: plan.start_date,
    end: plan.end_date,
    goalText: plan.goal_text ?? "",
    goalDate: plan.goal_date ?? "",
    hours: text(plan.hours_per_week),
    raceId: plan.race?.id ?? "",
    goalId: plan.goal?.id ?? "",
    phases: plan.phases.map(phaseDraft),
  };
}

/** "6,5" or "6.5" → 6.5; blank → null; anything else → NaN. */
export function parseHours(value: string): number | null {
  const trimmed = value.trim().replace(",", ".");
  return trimmed === "" ? null : Number(trimmed);
}

function draftPhases(draft: PlanDraft): Phase[] {
  return draft.phases.map((p) => ({
    kind: p.kind,
    name: p.name.trim() || null,
    start: p.start,
    end: p.end,
    focus: p.focus.trim() || null,
    hours: parseHours(p.hours),
  }));
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function draftErrors(draft: PlanDraft): PlanDraftErrors {
  const errors: PlanDraftErrors = {};
  if (draft.name.trim() === "") errors.name = true;
  const datesOk = DATE.test(draft.start) && DATE.test(draft.end) && draft.end >= draft.start && daysBetween(draft.start, draft.end) < MAX_PLAN_DAYS;
  if (!datesOk) errors.dates = true;
  if (draft.goalDate !== "" && datesOk && (draft.goalDate < draft.start || draft.goalDate > draft.end)) errors.goalDate = true;
  if (datesOk) {
    const problem = phaseProblem(draft.start, draft.end, draftPhases(draft));
    if (problem) errors.phases = problem;
  }
  return errors;
}

export function hasDraftErrors(errors: PlanDraftErrors): boolean {
  return Object.keys(errors).length > 0;
}

export function draftPayload(draft: PlanDraft): TrainingPlanWrite | null {
  if (hasDraftErrors(draftErrors(draft))) return null;
  const hours = parseHours(draft.hours);
  return {
    name: draft.name.trim(),
    sport: draft.sport,
    start_date: draft.start,
    end_date: draft.end,
    goal_text: draft.goalText.trim() || null,
    goal_date: draft.goalDate || null,
    // A time goal is a track event: a road plan never carries one.
    goal_id: draft.sport === "track_cycling" ? draft.goalId || null : null,
    competition_id: draft.raceId || null,
    hours_per_week: hours != null && Number.isFinite(hours) ? hours : null,
    phases: [...draftPhases(draft)]
      .map((p) => ({ ...p, hours: p.hours != null && Number.isFinite(p.hours) ? p.hours : null }))
      .sort((a, b) => a.start.localeCompare(b.start)),
  };
}

/** A race was picked: the plan aims at it, so it ends on race day and the goal date follows. */
export function withRace(draft: PlanDraft, raceId: string, raceDate: string | null): PlanDraft {
  if (!raceId || !raceDate) return { ...draft, raceId };
  return {
    ...draft,
    raceId,
    end: raceDate > draft.start ? raceDate : draft.end,
    goalDate: draft.goalDate === "" || draft.goalDate === draft.end ? raceDate : draft.goalDate,
  };
}

/** A new phase after the last one (or from the plan's start), a week long, inside the plan. */
export function addedPhase(draft: PlanDraft): PhaseDraft {
  const last = [...draft.phases].sort((a, b) => a.end.localeCompare(b.end)).at(-1);
  const start = last && DATE.test(last.end) ? addDays(last.end, 1) : draft.start;
  const end = addDays(start, 6) > draft.end ? draft.end : addDays(start, 6);
  return { kind: "build", name: "", start: start > draft.end ? draft.end : start, end, focus: "", hours: "" };
}
