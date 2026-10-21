import { describe, expect, it } from "vitest";
import { formFromTrack, invalidFields, payloadFromForm, withHidden } from "./trackSettingsForm";
import type { TrackSummary } from "./types";

const track: TrackSummary = {
  id: "t1",
  name: "Tour complet",
  length_m: 250,
  indoor: true,
  elevation_m: null,
  default_temp_c: 27.5,
  sqorz_name: null,
  city: null,
  region: null,
  country: null,
  latitude: null,
  longitude: null,
  width_m: null,
  surface: null,
  bank_straight_deg: null,
  bank_curve_deg: null,
  notes: null,
  can_edit: true,
  loops: [
    { id: "l1", name: "Courbe 1", distance_m: null, hidden: true },
    { id: "l2", name: "Finish", distance_m: 250, hidden: false },
  ],
  views: [
    { id: "v1", name: "200m", hidden: false },
    { id: "v2", name: "P2-P1-P2", hidden: true },
  ],
};

describe("track settings form", () => {
  it("starts from the saved settings", () => {
    expect(formFromTrack(track)).toEqual({
      length: "250",
      indoor: "indoor",
      elevation: "",
      temperature: "27.5",
      hiddenLoopIds: ["l1"],
      hiddenViewIds: ["v2"],
    });
  });

  it("maps unknown/outdoor, and blank numbers become null (cleared)", () => {
    const base = formFromTrack({ ...track, indoor: null, length_m: null, default_temp_c: null });
    expect(payloadFromForm(base)).toEqual({
      length_m: null,
      indoor: null,
      elevation_m: null,
      default_temp_c: null,
      hidden_loop_ids: ["l1"],
      hidden_view_ids: ["v2"],
    });
    expect(payloadFromForm({ ...base, indoor: "outdoor" }).indoor).toBe(false);
  });

  it("sends numbers, not strings", () => {
    const payload = payloadFromForm({ ...formFromTrack(track), length: "333.3", elevation: "-12", temperature: "0" });
    expect(payload.length_m).toBe(333.3);
    expect(payload.elevation_m).toBe(-12);
    expect(payload.default_temp_c).toBe(0);
  });

  it("flags only the values the backend would reject", () => {
    const form = formFromTrack(track);
    expect(invalidFields(form).size).toBe(0);
    expect([...invalidFields({ ...form, length: "0" })]).toEqual(["length"]);
    expect([...invalidFields({ ...form, length: "1001" })]).toEqual(["length"]);
    expect([...invalidFields({ ...form, elevation: "abc" })]).toEqual(["elevation"]);
    expect([...invalidFields({ ...form, temperature: "61" })]).toEqual(["temperature"]);
    expect(invalidFields({ ...form, length: "", elevation: "", temperature: "" }).size).toBe(0); // blank = clear
  });

  it("adds and removes hidden ids without duplicating", () => {
    expect(withHidden(["a"], "b", true)).toEqual(["a", "b"]);
    expect(withHidden(["a", "b"], "a", true)).toEqual(["b", "a"]);
    expect(withHidden(["a", "b"], "a", false)).toEqual(["b"]);
    expect(withHidden([], "a", false)).toEqual([]);
  });
});
