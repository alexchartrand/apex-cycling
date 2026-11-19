import { describe, expect, it } from "vitest";
import { cardShown, guessSports, pageShown, resolveSports, SPORTS, sportOfType } from "./registry";

describe("pageShown", () => {
  it("always shows pages every sport shares", () => {
    expect(pageShown("plans", new Set())).toBe(true);
    expect(pageShown("progress", new Set(["strength"]))).toBe(true);
  });

  it("shows sport pages only to their sports", () => {
    const strength = new Set(["strength"] as const);
    expect(pageShown("power", strength)).toBe(false);
    expect(pageShown("tools", strength)).toBe(false);
    const road = new Set(["cycling"] as const);
    expect(pageShown("power", road)).toBe(true);
    expect(pageShown("tools", road)).toBe(false);
    expect(pageShown("records", road)).toBe(false);
    expect(pageShown("records", new Set(["track_cycling"] as const))).toBe(true);
  });

  it("gates the track Home card", () => {
    expect(cardShown("track", new Set(["cycling"] as const))).toBe(false);
    expect(cardShown("track", new Set(["track_cycling"] as const))).toBe(true);
  });
});

describe("guessSports", () => {
  it("reads the data", () => {
    expect(guessSports({ hasTrack: true, activityTypes: ["indoor_cycling"] })).toEqual(new Set(["track_cycling", "cycling"]));
    expect(guessSports({ hasTrack: false, activityTypes: ["strength", "other"] })).toEqual(new Set(["strength"]));
  });

  it("shows everything to a new account", () => {
    expect(guessSports({ hasTrack: false, activityTypes: ["other"] })).toEqual(new Set(SPORTS));
  });
});

describe("resolveSports", () => {
  it("prefers the athlete's choice and ignores unknown sports", () => {
    expect(resolveSports(["cycling", "running"], () => new Set(SPORTS))).toEqual(new Set(["cycling"]));
    expect(resolveSports(null, () => new Set(["strength"] as const))).toEqual(new Set(["strength"]));
    expect(resolveSports(["running"], () => new Set(["strength"] as const))).toEqual(new Set(["strength"]));
  });

  it("maps activity types to sports", () => {
    expect(sportOfType("indoor_cycling")).toBe("cycling");
    expect(sportOfType("other")).toBeNull();
  });
});
