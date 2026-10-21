import { describe, expect, it } from "vitest";
import { bikeOfWeight, gearChoices, gearName, gearOf, parseNumber, weighedBikes } from "./gear";
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
});
