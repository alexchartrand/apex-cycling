import type { TrainingLoadDay } from "./types";

export type FormState = "fresh" | "balanced" | "loaded" | "overreaching";

/**
 * Where the rider's form (TSB: fitness minus fatigue going into the day)
 * puts them. The bands are the usual coaching rules of thumb, not a
 * prescription: fresh to race, balanced, productive load, risk of overdoing it.
 */
export function formState(tsb: number): FormState {
  if (tsb >= 5) return "fresh";
  if (tsb >= -10) return "balanced";
  if (tsb >= -30) return "loaded";
  return "overreaching";
}

export const FORM_TONE: Record<FormState, "positive" | "neutral" | "accent" | "negative"> = {
  fresh: "positive",
  balanced: "neutral",
  loaded: "accent",
  overreaching: "negative",
};

export interface LoadSummary {
  ctl: number;
  atl: number;
  tsb: number;
  /** Fitness change over the last 7 days. */
  ctlWeekChange: number;
  state: FormState;
}

export function summarizeLoad(days: TrainingLoadDay[]): LoadSummary | null {
  const last = days[days.length - 1];
  if (!last) return null;
  const weekAgo = days[Math.max(0, days.length - 8)];
  return { ctl: last.ctl, atl: last.atl, tsb: last.tsb, ctlWeekChange: last.ctl - weekAgo.ctl, state: formState(last.tsb) };
}

/** Rows for the chart: epoch-ms x so the time axis is true to the calendar. */
export function loadChartRows(days: TrainingLoadDay[]) {
  return days.map((d) => {
    const [y, m, day] = d.day.split("-").map(Number);
    return { t: new Date(y, m - 1, day).getTime(), ctl: d.ctl, atl: d.atl, tsb: d.tsb, tss: d.tss };
  });
}
