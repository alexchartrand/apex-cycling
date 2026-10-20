/*
  The trackside board's state: the coach starts the clock at the gun and taps
  each time the rider crosses a pursuit line; every tap is compared with the
  schedule, so the coach can signal "up" or "down" on the next pass.
*/

export type BoardState = { startedAt: number | null; taps: number[] };

export type BoardAction = { type: "start"; at: number } | { type: "tap"; at: number } | { type: "undo" } | { type: "reset" };

export const INITIAL_BOARD: BoardState = { startedAt: null, taps: [] };

export function boardReducer(state: BoardState, action: BoardAction): BoardState {
  switch (action.type) {
    case "start":
      return state.startedAt === null ? { startedAt: action.at, taps: [] } : state;
    case "tap":
      return state.startedAt === null ? state : { ...state, taps: [...state.taps, action.at] };
    case "undo":
      return { ...state, taps: state.taps.slice(0, -1) };
    case "reset":
      return INITIAL_BOARD;
  }
}

/** Seconds ahead (negative) or behind (positive) the schedule at each tapped crossing. */
export function tapDeltas(state: BoardState, scheduleElapsedS: number[]): number[] {
  if (state.startedAt === null) return [];
  const start = state.startedAt;
  return state.taps
    .slice(0, scheduleElapsedS.length)
    .map((at, i) => (at - start) / 1000 - scheduleElapsedS[i]);
}

/** Within this many seconds of the schedule counts as on pace. */
export const ON_PACE_S = 0.15;

export type Pace = "ahead" | "onPace" | "behind";

export function paceOf(deltaS: number): Pace {
  if (deltaS < -ON_PACE_S) return "ahead";
  if (deltaS > ON_PACE_S) return "behind";
  return "onPace";
}
