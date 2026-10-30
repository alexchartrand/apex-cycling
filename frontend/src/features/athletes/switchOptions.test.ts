import { describe, expect, it } from "vitest";
import { buildSwitchOptions } from "./switchOptions";

const me = { id: "me", name: "Alex" };

describe("buildSwitchOptions", () => {
  it("is just the user when nobody else is reachable", () => {
    expect(buildSwitchOptions({ me, rosters: [] })).toEqual([{ athleteId: "me", name: "Alex", group: "me" }]);
  });

  it("lists me, then club rosters, each sorted by name", () => {
    const options = buildSwitchOptions({
      me,
      rosters: [{ clubName: "CNCB", athletes: [{ id: "r2", display_name: "Yan" }, { id: "r1", display_name: "Anna" }] }],
    });
    expect(options.map((o) => [o.group, o.name])).toEqual([
      ["me", "Alex"],
      ["club", "Anna"],
      ["club", "Yan"],
    ]);
    expect(options.at(-1)?.clubName).toBe("CNCB");
  });

  it("lists an athlete once, however many rosters they are on, and never the user twice", () => {
    const options = buildSwitchOptions({
      me,
      rosters: [
        { clubName: "CNCB", athletes: [{ id: "x", display_name: "Xavier" }, { id: "me", display_name: "Alex" }] },
        { clubName: "VCL", athletes: [{ id: "x", display_name: "Xavier" }] },
      ],
    });
    expect(options.map((o) => [o.athleteId, o.group, o.clubName])).toEqual([
      ["me", "me", undefined],
      ["x", "club", "CNCB"],
    ]);
  });

  it("waits for the user's own athlete before listing it", () => {
    expect(buildSwitchOptions({ me: undefined, rosters: [] })).toEqual([]);
  });
});
