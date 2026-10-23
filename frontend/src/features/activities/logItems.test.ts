import { describe, expect, it } from "vitest";
import type { SessionSummary } from "../training/types";
import { groupItemsByMonth, mergeLog, monthCalendar } from "./logItems";
import type { Activity } from "./types";

function session(id: string, date: string): SessionSummary {
  return { external_event_id: id, event_name: id, event_date: date, lap_count: 10, track_names: [], rpe: null, tags: [], is_race: false, first_lap_at: `${date}T18:00:00Z`, last_lap_at: null };
}

function activity(id: string, startLocal: [number, number, number], eventId: string | null = null): Activity {
  return {
    id, start_time: new Date(startLocal[0], startLocal[1] - 1, startLocal[2], 9, 0).toISOString(), external_event_id: eventId,
  } as Activity;
}

describe("mergeLog", () => {
  it("folds a recording into the session it belongs to and keeps loose rides as rows", () => {
    const items = mergeLog(
      [session("s1", "2026-06-05"), session("s2", "2026-06-01")],
      [activity("a1", [2026, 6, 5], "s1"), activity("a2", [2026, 6, 3])],
    );

    expect(items.map((i) => i.kind)).toEqual(["session", "activity", "session"]);
    expect(items[0]).toMatchObject({ kind: "session", activities: [{ id: "a1" }] });
    expect(items[1]).toMatchObject({ kind: "activity", day: "2026-06-03" });
  });

  it("treats a link to a session that isn't listed as a loose ride", () => {
    const items = mergeLog([session("s1", "2026-06-05")], [activity("a1", [2026, 6, 6], "gone")]);
    expect(items.map((i) => i.kind)).toEqual(["activity", "session"]);
  });

  it("orders a session and a ride of the same day by time, newest first", () => {
    const items = mergeLog([session("s1", "2026-06-05")], [activity("early", [2026, 6, 5])]);
    // The session's first lap is at 18:00Z, after the 9:00 ride.
    expect(items.map((i) => (i.kind === "session" ? i.session.external_event_id : i.activity.id))).toEqual(["s1", "early"]);
  });
});

describe("groupItemsByMonth", () => {
  it("groups consecutive items under their month", () => {
    const groups = groupItemsByMonth(mergeLog([session("a", "2026-07-02"), session("b", "2026-06-30"), session("c", "2026-06-01")], []));
    expect(groups.map((g) => [g.month, g.items.length])).toEqual([["2026-07", 1], ["2026-06", 2]]);
  });
});

describe("monthCalendar", () => {
  it("lays out Monday-first weeks around the month", () => {
    const weeks = monthCalendar(2026, 5, []); // June 2026 starts on a Monday and ends on a Tuesday
    expect(weeks).toHaveLength(5);
    expect(weeks[0][0]).toMatchObject({ day: "2026-06-01", inMonth: true });
    expect(weeks[4][1]).toMatchObject({ day: "2026-06-30", inMonth: true });
    expect(weeks[4][2]).toMatchObject({ day: "2026-07-01", inMonth: false });
    expect(weeks.every((w) => w.length === 7)).toBe(true);
  });

  it("starts with the previous month's days when the month begins midweek", () => {
    const weeks = monthCalendar(2026, 6, []); // July 1st 2026 is a Wednesday
    expect(weeks[0].map((d) => d.day)).toEqual(["2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"]);
    expect(weeks[0].map((d) => d.inMonth)).toEqual([false, false, true, true, true, true, true]);
  });

  it("puts each log item on its day", () => {
    const items = mergeLog([session("s1", "2026-06-05")], [activity("a1", [2026, 6, 5]), activity("a2", [2026, 6, 20])]);
    const days = monthCalendar(2026, 5, items).flat();
    expect(days.find((d) => d.day === "2026-06-05")?.items).toHaveLength(2);
    expect(days.find((d) => d.day === "2026-06-20")?.items).toHaveLength(1);
    expect(days.find((d) => d.day === "2026-06-06")?.items).toHaveLength(0);
  });

  it("covers a February that fits exactly four weeks", () => {
    expect(monthCalendar(2027, 1, [])).toHaveLength(4); // Feb 2027: Mon 1st – Sun 28th
  });
});
