import { powerForTimeW, simulate, type Setup } from "./physics";

/** One pursuit-line crossing (every half lap, P1/P2) on the schedule. */
export type ScheduleRow = {
  /** 1-based count of half laps ridden at this crossing. */
  halfLap: number;
  distanceM: number;
  /** Target elapsed time at the crossing. */
  elapsedS: number;
  /** Time since the previous crossing. */
  splitS: number;
  /** Whole-lap number when this crossing completes a lap, else null. */
  lap: number | null;
  /** That lap's time, for whole-lap crossings. */
  lapS: number | null;
};

export type Schedule = {
  /** Race power that rides the target (above it during a standing start). */
  powerW: number;
  /** Average power over the whole effort, start included. */
  averagePowerW: number;
  rows: ScheduleRow[];
};

/**
 * A half-lap schedule for a target time, shaped by the physics model: the
 * standing first half laps are slow, then the pace settles. Times are scaled
 * by the (sub-millisecond) bisection error so the last row is the target
 * exactly. Null when no power under 3000 W makes the target.
 */
export function pursuitSchedule(
  distanceM: number,
  targetS: number,
  lapM: number,
  setup: Setup,
  standing = true,
): Schedule | null {
  const powerW = powerForTimeW(distanceM, targetS, setup, { standing });
  if (powerW === null) return null;
  const ride = simulate(distanceM, powerW, setup, { standing, splitEveryM: lapM / 2 });
  if (ride === null) return null;
  const scale = targetS / ride.timeS;
  const elapsed = [...ride.splitTimesS, ride.timeS].map((t) => t * scale);
  const rows = elapsed.map((elapsedS, i): ScheduleRow => {
    const halfLap = i + 1;
    const isLast = i === elapsed.length - 1;
    const wholeLap = halfLap % 2 === 0;
    return {
      halfLap,
      distanceM: isLast ? distanceM : (halfLap * lapM) / 2,
      elapsedS,
      splitS: elapsedS - (i > 0 ? elapsed[i - 1] : 0),
      lap: wholeLap ? halfLap / 2 : null,
      lapS: wholeLap ? elapsedS - (i > 1 ? elapsed[i - 2] : 0) : null,
    };
  });
  return { powerW, averagePowerW: ride.averagePowerW, rows };
}

/**
 * A ridden effort's elapsed time at the end of each lap, for laying it over
 * the schedule. Stops at the first unfinished lap: nothing after it is known.
 */
export function effortElapsedByLap(lapTimesMs: (number | null)[]): number[] {
  const elapsed: number[] = [];
  let total = 0;
  for (const ms of lapTimesMs) {
    if (ms === null) break;
    total += ms / 1000;
    elapsed.push(total);
  }
  return elapsed;
}
