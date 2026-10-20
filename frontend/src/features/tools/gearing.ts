import { developmentM, speedFromCadenceMs } from "./physics";

export const TABLE_CADENCES = [80, 90, 100, 110, 120, 130, 140, 150];

export type CadenceRow = { cadenceRpm: number; speedKmh: number; lapS: number; flying200S: number };

/** Speed, lap time and flying-200 time at each cadence, for one gear on one track. */
export function cadenceTable(chainring: number, cog: number, rolloutM: number, lapM: number, cadences = TABLE_CADENCES): CadenceRow[] {
  return cadences.map((cadenceRpm) => {
    const speed = speedFromCadenceMs(cadenceRpm, chainring, cog, rolloutM);
    return { cadenceRpm, speedKmh: speed * 3.6, lapS: lapM / speed, flying200S: 200 / speed };
  });
}

/** Cadence needed to ride one lap in `lapS` with this gear. */
export function cadenceForLapTime(lapS: number, lapM: number, chainring: number, cog: number, rolloutM: number): number {
  return (lapM / lapS / developmentM(chainring, cog, rolloutM)) * 60;
}
