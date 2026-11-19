import type { Phase, PhaseKind, TrainingPlan } from "./types";

const DAY_MS = 86_400_000;

/** Days from `a` to `b` (YYYY-MM-DD), whole days, with no time zone drift. */
export function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / DAY_MS);
}

export function addDays(day: string, days: number): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

export interface TimelineBlock {
  phase: Phase;
  index: number;
  /** Position and size in % of the plan's length. */
  left: number;
  width: number;
}

export interface Timeline {
  days: number;
  blocks: TimelineBlock[];
  /** Where today sits, in %; null outside the plan. */
  today: number | null;
  /** Monday week ticks, in %, with their date. */
  weeks: { left: number; day: string }[];
  race: number | null;
}

/** The plan's phases laid out on its span (pure; drawn by `PhaseTimeline`). */
export function timeline(start: string, end: string, phases: Phase[], today: string, raceDate?: string | null): Timeline {
  const days = daysBetween(start, end) + 1;
  const pct = (day: string) => (daysBetween(start, day) / days) * 100;
  const blocks = phases.map((phase, index) => ({
    phase,
    index,
    left: pct(phase.start),
    width: ((daysBetween(phase.start, phase.end) + 1) / days) * 100,
  }));
  const offset = daysBetween(start, today);
  const weeks: { left: number; day: string }[] = [];
  const weekday = (new Date(`${start}T00:00:00Z`).getUTCDay() + 6) % 7; // 0 = Monday
  for (let day = weekday === 0 ? 0 : 7 - weekday; day < days; day += 7) {
    weeks.push({ left: (day / days) * 100, day: addDays(start, day) });
  }
  const raceOffset = raceDate ? daysBetween(start, raceDate) : -1;
  return {
    days,
    blocks,
    today: offset >= 0 && offset < days ? ((offset + 0.5) / days) * 100 : null,
    weeks,
    race: raceOffset >= 0 && raceOffset < days ? ((raceOffset + 0.5) / days) * 100 : null,
  };
}

export function phaseColor(kind: PhaseKind): string {
  return `var(--color-phase-${kind})`;
}

/** Why a set of phases can't be saved: the first problem, as an i18n key under `errors.`. */
export function phaseProblem(start: string, end: string, phases: Phase[]): "phaseOrder" | "phaseOutside" | "phaseOverlap" | null {
  const sorted = [...phases].sort((a, b) => a.start.localeCompare(b.start));
  for (const phase of sorted) {
    if (!phase.start || !phase.end || phase.end < phase.start) return "phaseOrder";
    if (phase.start < start || phase.end > end) return "phaseOutside";
  }
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].start <= sorted[i - 1].end) return "phaseOverlap";
  }
  return null;
}

/** The plan a session on `day` most likely belongs to: the only plan covering that day (else none). */
export function defaultPlanFor(plans: TrainingPlan[], day: string): string | null {
  const covering = plans.filter((plan) => plan.start_date <= day && day <= plan.end_date);
  return covering.length === 1 ? covering[0].id : null;
}

/** How far into the plan today is, 0…1. */
export function elapsedShare(start: string, end: string, today: string): number {
  const days = daysBetween(start, end) + 1;
  return Math.min(1, Math.max(0, (daysBetween(start, today) + 1) / days));
}
