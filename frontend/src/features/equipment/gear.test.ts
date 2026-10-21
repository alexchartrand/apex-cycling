import { describe, expect, it } from "vitest";
import { gearChoices, gearName, parseNumber } from "./gear";
import type { Bike } from "./types";

const gear = { bike_id: "b", rollout_mm: 2100, tire: null, ratio: 0, development_m: 0, gear_inches: 0 };
const bike = (id: string, name: string, gears: [string, number, number][]): Bike => ({
  id,
  name,
  weight_kg: null,
  notes: null,
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

  it("reads numbers with a decimal comma and rejects text", () => {
    expect(parseNumber("7,4")).toBe(7.4);
    expect(parseNumber(" 2105 ")).toBe(2105);
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("abc")).toBeNull();
  });
});
