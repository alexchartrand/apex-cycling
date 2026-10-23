import { describe, expect, it } from "vitest";
import tires from "./tires.json";
import { bikeOfWeight, bikeRolloutMm, bikeTireSizeMm, gearChoices, gearName, gearOf, parseNumber, rolloutPresetOf, standardTireOf, STANDARD_TIRES, tireLabel, tiresByBrand, weighedBikes } from "./gear";
import { GEAR_BOUNDS } from "./types";
import type { Bike } from "./types";

const gear = { bike_id: "b", rollout_mm: 2100, ratio: 0, development_m: 0, gear_inches: 0 };
const bike = (id: string, name: string, gears: [string, number, number][]): Bike => ({
  id,
  name,
  weight_kg: null,
  notes: null,
  tire: null,
  crr: null,
  gears: gears.map(([gid, chainring_teeth, cog_teeth]) => ({ ...gear, id: gid, chainring_teeth, cog_teeth })),
});

describe("gear", () => {
  it("names a gear chainring × cog", () => {
    expect(gearName({ chainring_teeth: 50, cog_teeth: 15 })).toBe("50×15");
  });

  it("lists every gear of every bike with its bike", () => {
    const bikes = [bike("1", "Track", [["g1", 50, 15], ["g2", 52, 14]]), bike("2", "Pursuit", []), bike("3", "Road", [["g3", 53, 12]])];
    expect(gearChoices(bikes)).toEqual([
      { id: "g1", label: "Track · 50×15" },
      { id: "g2", label: "Track · 52×14" },
      { id: "g3", label: "Road · 53×12" },
    ]);
  });

  it("finds the bike a weight belongs to, among the weighed ones", () => {
    const bikes = [bike("1", "Unweighed", []), { ...bike("2", "Track", []), weight_kg: 7.4 }, { ...bike("3", "Spare", []), weight_kg: 7.4 }];
    expect(weighedBikes(bikes).map((b) => b.id)).toEqual(["2", "3"]);
    expect(bikeOfWeight(bikes, 7.4)?.id).toBe("2");
    expect(bikeOfWeight(bikes, 8)).toBeNull();
    expect(bikeOfWeight(bikes, null)).toBeNull();
  });

  it("finds the saved gear from its teeth and rollout", () => {
    const bikes = [bike("1", "Track", [["g1", 50, 15], ["g2", 52, 14]])];
    expect(gearOf(bikes, 52, 14, 2100.2)?.id).toBe("g2");
    expect(gearOf(bikes, 52, 14, 2105)).toBeNull();
    expect(gearOf(bikes, 52, null, 2100)).toBeNull();
  });

  it("reads numbers with a decimal comma and rejects text", () => {
    expect(parseNumber("7,4")).toBe(7.4);
    expect(parseNumber(" 2105 ")).toBe(2105);
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("abc")).toBeNull();
  });

  it("names the standard tire a rollout belongs to", () => {
    expect(rolloutPresetOf(2105)?.tire).toBe("700×25c");
    expect(rolloutPresetOf(2.096 * 1000)?.tire).toBe("700×23c");
    expect(rolloutPresetOf(2100)).toBeNull();
    expect(rolloutPresetOf(null)).toBeNull();
  });
});

describe("standard tires", () => {
  const vittoria = { brand: "Vittoria", name: "Pista Control", type: "tubular", size: 23, crr: 0.001579 };
  const list = [{ ...vittoria, label: tireLabel(vittoria) }];

  it("labels a tire brand, name, type, size", () => {
    expect(tireLabel(vittoria)).toBe("Vittoria Pista Control tubular 23 mm");
  });

  it("finds the listed tire from its label and Crr", () => {
    expect(standardTireOf("  vittoria pista  control tubular 23 mm ", 0.001579, list)).toEqual(list[0]);
    expect(standardTireOf("Vittoria Pista Control tubular 23 mm", 0.002, list)).toBeNull();
    expect(standardTireOf("Vittoria Pista Control tubular 23 mm", null, list)).toBeNull();
    expect(standardTireOf("My tire", 0.001579, list)).toBeNull();
  });

  it("groups by brand", () => {
    const other = { ...vittoria, brand: "Continental", name: "Pro Track", label: "x" };
    expect(tiresByBrand([list[0], other, list[0]]).map(([brand, tires]) => [brand, tires.length])).toEqual([
      ["Vittoria", 2],
      ["Continental", 1],
    ]);
  });

  it("keeps tires.json valid: every field filled, a unique label and a Crr the API accepts", () => {
    expect(STANDARD_TIRES).toHaveLength(tires.length);
    expect(new Set(STANDARD_TIRES.map((tire) => tire.label.toLowerCase())).size).toBe(tires.length);
    for (const tire of STANDARD_TIRES) {
      expect(Number.isInteger(tire.size) && tire.size >= 15 && tire.size <= 60, `${tire.label}: size in whole mm`).toBe(true);
      for (const field of ["brand", "name", "type"] as const) {
        expect(typeof tire[field] === "string" && tire[field].trim() !== "", `${tire.label}: ${field}`).toBe(true);
      }
      expect(tire.label.length, tire.label).toBeLessThanOrEqual(100);
      expect(typeof tire.crr, tire.label).toBe("number");
      expect(tire.crr, tire.label).toBeGreaterThanOrEqual(GEAR_BOUNDS.crr.min);
      expect(tire.crr, tire.label).toBeLessThanOrEqual(GEAR_BOUNDS.crr.max);
    }
  });

  it("derives a bike's tire size and standard rollout from its tire", () => {
    expect(bikeTireSizeMm({ tire: "Vittoria Pista Control tubular 23 mm" })).toBe(23);
    expect(bikeTireSizeMm({ tire: "Some tire 25mm clincher" })).toBe(25);
    expect(bikeTireSizeMm({ tire: null })).toBeNull();
    expect(bikeTireSizeMm({ tire: "Mystery tire" })).toBeNull();
    expect(bikeRolloutMm({ tire: "Vittoria Pista Control tubular 23 mm" })).toBe(2096);
    expect(bikeRolloutMm({ tire: "Some tire 25 mm" })).toBe(2105);
    expect(bikeRolloutMm({ tire: "Continental Sprinter tubular 22 mm" })).toBeNull();
    expect(bikeRolloutMm({ tire: null })).toBeNull();
  });
});
