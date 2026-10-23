import type { Competition, CompetitionWrite, Priority, SeasonWrite } from "./types";

export type CompetitionForm = {
  name: string;
  date: string;
  priority: Priority;
  location: string;
  notes: string;
  /** "" = no goal. */
  goalId: string;
};

export function emptyCompetitionForm(): CompetitionForm {
  return { name: "", date: "", priority: "B", location: "", notes: "", goalId: "" };
}

export function competitionFormFrom(competition: Competition): CompetitionForm {
  return {
    name: competition.name,
    date: competition.competition_date,
    priority: competition.priority,
    location: competition.location ?? "",
    notes: competition.notes ?? "",
    goalId: competition.goal?.id ?? "",
  };
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;

export type CompetitionFormErrors = { name?: true; date?: true };

export function competitionFormErrors(form: CompetitionForm): CompetitionFormErrors {
  const errors: CompetitionFormErrors = {};
  if (!form.name.trim()) errors.name = true;
  if (!DATE.test(form.date)) errors.date = true;
  return errors;
}

export function competitionPayload(form: CompetitionForm): CompetitionWrite | null {
  const errors = competitionFormErrors(form);
  if (errors.name || errors.date) return null;
  return {
    name: form.name.trim(),
    competition_date: form.date,
    priority: form.priority,
    location: form.location.trim() || null,
    notes: form.notes.trim() || null,
    goal_id: form.goalId || null,
  };
}

export type SeasonForm = { name: string; start: string };

/** A new season: named for the calendar year, starting on 1 January. */
export function defaultSeasonForm(today: string): SeasonForm {
  const year = today.slice(0, 4);
  return { name: year, start: `${year}-01-01` };
}

export function seasonPayload(form: SeasonForm): SeasonWrite | null {
  if (!form.name.trim() || !DATE.test(form.start)) return null;
  return { name: form.name.trim(), start_date: form.start };
}

/** The race the Home card talks about: the first one still ahead (they arrive soonest first). */
export function nextCompetition(competitions: Competition[]): Competition | null {
  return competitions.find((competition) => competition.days_until >= 0) ?? null;
}

/** "−1.2 s" style improvement of a season best over what the rider had before, in ms; null without a previous best. */
export function improvementMs(best: { time_ms: number; previous_best_ms: number | null }): number | null {
  return best.previous_best_ms == null ? null : best.previous_best_ms - best.time_ms;
}
