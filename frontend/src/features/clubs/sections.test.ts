import { describe, expect, it } from "vitest";
import { sectionsFor } from "./sections";

describe("sectionsFor", () => {
  it("gives admins everything", () => {
    expect(sectionsFor("club_admin")).toEqual(["members", "athletes", "leaderboard", "invites", "tracks", "settings"]);
  });

  it("gives coaches the roster but not the admin sections", () => {
    expect(sectionsFor("coach")).toEqual(["members", "athletes", "leaderboard", "tracks"]);
  });

  it("gives athletes the club without the roster", () => {
    expect(sectionsFor("athlete")).toEqual(["members", "leaderboard", "tracks"]);
  });
});
