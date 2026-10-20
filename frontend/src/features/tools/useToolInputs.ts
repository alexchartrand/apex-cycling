import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useActiveAthlete } from "../athletes/useActiveAthlete";
import { useCurrentMetrics } from "../athletes/useAthlete";
import { useTracks } from "../training/useTraining";
import type { TrackSummary } from "../training/types";
import { airDensity, makeSetup, type Setup } from "./physics";
import {
  FALLBACK_TIME,
  MODE_PARAM,
  NUMBER_FIELDS,
  START_PARAM,
  TIME_PARAM,
  TRACK_PARAM,
  rawValue,
  readNumberField,
  readTimeField,
  shareQuery,
  type FieldState,
  type NumberKey,
  type StartKind,
} from "./toolInputs";

/** Values a track fills in; picking another track drops them from the URL. */
const TRACK_KEYS: NumberKey[] = ["lapM", "elevationM", "tempC"];
/** `?track=none` keeps the URL from falling back to the first track. */
export const NO_TRACK = "none";

/**
 * The tools' shared inputs, read from the URL with the active athlete's
 * weight and track facts as defaults (see toolInputs.ts). Setters write to
 * the URL (replacing the history entry, so typing doesn't stack up Back steps).
 */
export function useToolInputs() {
  const [params, setParams] = useSearchParams();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const metrics = useCurrentMetrics(athleteId);
  const tracksQuery = useTracks(athleteId);

  const tracks = useMemo(() => tracksQuery.data ?? [], [tracksQuery.data]);
  const trackParam = params.get(TRACK_PARAM);
  const track: TrackSummary | null =
    trackParam === NO_TRACK
      ? null
      : (tracks.find((candidate) => candidate.id === trackParam) ??
        (trackParam === null ? (tracks.find((candidate) => candidate.length_m != null) ?? null) : null));

  const weight = metrics.data?.weight_kg?.value ?? null;
  const prefill = useMemo(
    () => ({
      riderKg: weight,
      lapM: track?.length_m ?? null,
      elevationM: track?.elevation_m ?? null,
      tempC: track?.default_temp_c ?? null,
    }),
    [weight, track],
  );

  const field = useCallback(
    (key: NumberKey): FieldState => readNumberField(key, rawValue(params, key, prefill)),
    [params, prefill],
  );
  const timeRaw = params.get(TIME_PARAM) ?? FALLBACK_TIME;
  const start: StartKind = params.get(START_PARAM) === "flying" ? "flying" : "standing";

  const update = useCallback(
    (change: (next: URLSearchParams) => void) =>
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          change(next);
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );

  const set = useCallback(
    (key: NumberKey, raw: string) => update((next) => next.set(NUMBER_FIELDS[key].param, raw)),
    [update],
  );
  const setParam = useCallback((param: string, value: string) => update((next) => next.set(param, value)), [update]);
  const setTrack = useCallback(
    (trackId: string) =>
      update((next) => {
        next.set(TRACK_PARAM, trackId || NO_TRACK);
        for (const key of TRACK_KEYS) next.delete(NUMBER_FIELDS[key].param);
      }),
    [update],
  );

  /** Air density from the air inputs; null while one of them is invalid. */
  const rho = useMemo(() => {
    const temp = field("tempC");
    const elevation = field("elevationM");
    const humidity = field("humidityPct");
    const pressure = field("pressureHpa");
    if ([temp, elevation, humidity, pressure].some((f) => f.invalid)) return null;
    return airDensity(temp.value!, {
      pressurePa: pressure.value === null ? null : pressure.value * 100,
      elevationM: elevation.value!,
      humidityPct: humidity.value!,
    });
  }, [field]);

  /** The rider's setup; null while an input is invalid. */
  const setup = useMemo((): Setup | null => {
    const values = (["riderKg", "bikeKg", "cda", "crr", "efficiencyPct"] as const).map(field);
    if (rho === null || values.some((f) => f.invalid)) return null;
    const [rider, bike, cda, crr, efficiency] = values.map((f) => f.value!);
    return makeSetup({ massKg: rider + bike, cdaM2: cda, rho, crr, efficiency: efficiency / 100 });
  }, [field, rho]);

  /** Query string reproducing these keys' current values exactly. */
  const shareSearch = useCallback(
    (keys: NumberKey[], extra: { time?: boolean; start?: boolean; mode?: boolean } = {}) =>
      shareQuery({
        ...(track ? { [TRACK_PARAM]: track.id } : {}),
        ...Object.fromEntries(keys.map((key) => [NUMBER_FIELDS[key].param, field(key).raw])),
        ...(extra.time ? { [TIME_PARAM]: timeRaw } : {}),
        ...(extra.start ? { [START_PARAM]: start } : {}),
        ...(extra.mode ? { [MODE_PARAM]: params.get(MODE_PARAM) } : {}),
      }),
    [track, field, timeRaw, start, params],
  );

  return {
    params,
    field,
    set,
    setParam,
    tracks,
    track,
    setTrack,
    weightFromProfile: weight !== null && !params.has(NUMBER_FIELDS.riderKg.param),
    time: readTimeField(timeRaw),
    start,
    rho,
    setup,
    shareSearch,
  };
}

export type ToolInputs = ReturnType<typeof useToolInputs>;

export const SETUP_KEYS: NumberKey[] = ["riderKg", "bikeKg", "cda", "crr", "efficiencyPct"];
export const AIR_KEYS: NumberKey[] = ["tempC", "elevationM", "humidityPct", "pressureHpa"];
