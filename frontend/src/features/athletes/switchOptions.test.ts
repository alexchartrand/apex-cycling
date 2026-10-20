import { describe, expect, it } from "vitest";
import { buildSwitchOptions } from "./switchOptions";

const me = { id: "me", name: "Alex" };

describe("buildSwitchOptions", () => {
  it("is just the user when nobody else is reachable", () => {
    expect(buildSwitchOptions({ me, coached: [], rosters: [] })).toEqual([{ athleteId: "me", name: "Alex", group: "me" }]);
  });

  it("lists me, then coached athletes, then club rosters, each sorted by name", () => {
    const options = buildSwitchOptions({
      me,
      coached: [
        { athlete_id: "c2", athlete_name: "Zoé", status: "active" },
        { athlete_id: "c1", athlete_name: "Bruno", status: "active" },
      ],
      rosters: [{ clubName: "CNCB", athletes: [{ id: "r2", display_name: "Yan" }, { id: "r1", display_name: "Anna" }] }],
    });
    expect(options.map((o) => [o.group, o.name])).toEqual([
      ["me", "Alex"],
      ["coached", "Bruno"],
      ["coached", "Zoé"],
      ["club", "Anna"],
      ["club", "Yan"],
    ]);
    expect(options.at(-1)?.clubName).toBe("CNCB");
  });

  it("only offers links that are active", () => {
    const options = buildSwitchOptions({
      me,
      coached: [
        { athlete_id: "a", athlete_name: "Waiting", status: "pending_athlete_acceptance" },
        { athlete_id: "b", athlete_name: "Ended", status: "revoked" },
      ],
      rosters: [],
    });
    expect(options).toHaveLength(1);
  });

  it("lists an athlete once, however they are reachable, and never the user twice", () => {
    const options = buildSwitchOptions({
      me,
      coached: [{ athlete_id: "x", athlete_name: "Xavier", status: "active" }],
      rosters: [{ clubName: "CNCB", athletes: [{ id: "x", display_name: "Xavier" }, { id: "me", display_name: "Alex" }] }],
    });
    expect(options.map((o) => [o.athleteId, o.group])).toEqual([
      ["me", "me"],
      ["x", "coached"],
    ]);
  });

  it("waits for the user's own athlete before listing it", () => {
    expect(buildSwitchOptions({ me: undefined, coached: [], rosters: [] })).toEqual([]);
  });
});
