import type { TrackSummary, TrackUpdate } from "./types";

export type IndoorChoice = "unknown" | "indoor" | "outdoor";

export type TrackSettingsForm = {
  length: string;
  indoor: IndoorChoice;
  elevation: string;
  temperature: string;
  hiddenLoopIds: string[];
  hiddenViewIds: string[];
};

// Mirrors the backend's TrackUpdate bounds.
export const TRACK_BOUNDS = {
  length: { min: 1, max: 1000, step: 0.1 },
  elevation: { min: -500, max: 6000, step: 1 },
  temperature: { min: -40, max: 60, step: 0.5 },
};

const numberOrEmpty = (value: number | null) => (value == null ? "" : String(value));

export function formFromTrack(track: TrackSummary): TrackSettingsForm {
  return {
    length: numberOrEmpty(track.length_m),
    indoor: track.indoor == null ? "unknown" : track.indoor ? "indoor" : "outdoor",
    elevation: numberOrEmpty(track.elevation_m),
    temperature: numberOrEmpty(track.default_temp_c),
    hiddenLoopIds: track.loops.filter((loop) => loop.hidden).map((loop) => loop.id),
    hiddenViewIds: track.views.filter((view) => view.hidden).map((view) => view.id),
  };
}

function inBounds(raw: string, bounds: { min: number; max: number }): boolean {
  if (raw.trim() === "") return true;
  const value = Number(raw);
  return Number.isFinite(value) && value >= bounds.min && value <= bounds.max;
}

/** Which numeric fields hold something the backend would reject. */
export function invalidFields(form: TrackSettingsForm): Set<"length" | "elevation" | "temperature"> {
  const invalid = new Set<"length" | "elevation" | "temperature">();
  if (!inBounds(form.length, TRACK_BOUNDS.length)) invalid.add("length");
  if (!inBounds(form.elevation, TRACK_BOUNDS.elevation)) invalid.add("elevation");
  if (!inBounds(form.temperature, TRACK_BOUNDS.temperature)) invalid.add("temperature");
  return invalid;
}

const toNumber = (raw: string) => (raw.trim() === "" ? null : Number(raw));

export function payloadFromForm(form: TrackSettingsForm): TrackUpdate {
  return {
    length_m: toNumber(form.length),
    indoor: form.indoor === "unknown" ? null : form.indoor === "indoor",
    elevation_m: toNumber(form.elevation),
    default_temp_c: toNumber(form.temperature),
    hidden_loop_ids: form.hiddenLoopIds,
    hidden_view_ids: form.hiddenViewIds,
  };
}

/** `ids` with `id` added (when `hidden`) or removed. */
export function withHidden(ids: string[], id: string, hidden: boolean): string[] {
  const without = ids.filter((existing) => existing !== id);
  return hidden ? [...without, id] : without;
}
