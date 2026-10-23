export type ChecklistStepKey = "transponder" | "physiology" | "club" | "coach";

export interface ChecklistInput {
  /** Transponders reported so far (any period). */
  transponders: number;
  weightKg: number | null;
  clubs: number;
  /** Coaching links that are active. */
  activeCoaches: number;
}

export interface ChecklistStep {
  key: ChecklistStepKey;
  done: boolean;
  /** Where to do it. */
  to: string;
  /** The steps that aren't needed to get value from the app. */
  optional: boolean;
}

export interface Checklist {
  steps: ChecklistStep[];
  doneCount: number;
  total: number;
  complete: boolean;
}

/** The first-run steps in the order they pay off: laps first, then W/kg, then people. */
export function buildChecklist(input: ChecklistInput): Checklist {
  const steps: ChecklistStep[] = [
    { key: "transponder", done: input.transponders > 0, to: "/import#sqorz", optional: false },
    { key: "physiology", done: input.weightKg != null, to: "/settings/physiology", optional: false },
    { key: "club", done: input.clubs > 0, to: "/club", optional: true },
    { key: "coach", done: input.activeCoaches > 0, to: "/coach", optional: true },
  ];
  const doneCount = steps.filter((step) => step.done).length;
  return { steps, doneCount, total: steps.length, complete: doneCount === steps.length };
}

const dismissKey = (athleteId: string) => `apex-checklist-dismissed:${athleteId}`;

/** A per-browser convenience, so it can be missing or blocked without harm. */
export function isDismissed(athleteId: string): boolean {
  try {
    return localStorage.getItem(dismissKey(athleteId)) === "1";
  } catch {
    return false;
  }
}

export function dismiss(athleteId: string): void {
  try {
    localStorage.setItem(dismissKey(athleteId), "1");
  } catch {
    // The checklist just comes back next visit.
  }
}

/** Total laps and sessions of a session list, for "found N laps". */
export function lapTotals(sessions: { lap_count: number }[]): { laps: number; sessions: number } {
  return { laps: sessions.reduce((sum, session) => sum + session.lap_count, 0), sessions: sessions.length };
}
