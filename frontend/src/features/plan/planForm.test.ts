import { describe, expect, it } from "vitest";
import { emptyEffortRow, emptyPlanForm, hasPlanErrors, linkCandidates, outstanding, planFormErrors, planFormFrom, planPayload, withRowEvent } from "./planForm";
import type { PlannedSession } from "./types";

const plan = (over: Partial<PlannedSession> = {}): PlannedSession => ({
  id: "p",
  planned_date: "2026-11-10",
  title: "Kilo openers",
  description: null,
  targets: [],
  status: "planned",
  created_by_name: null,
  session: null,
  can_edit: true,
  can_mark: true,
  ...over,
});

describe("plan form", () => {
  it("needs a title and a date, and each block a label and sane reps", () => {
    const form = emptyPlanForm("");
    expect(planFormErrors(form)).toEqual({ title: true, date: true, targets: {} });
    const ok = { ...emptyPlanForm("2026-11-10"), title: "Openers", targets: [{ ...emptyEffortRow(), label: "Tempo" }] };
    expect(hasPlanErrors(planFormErrors(ok))).toBe(false);
    expect(planFormErrors({ ...ok, targets: [emptyEffortRow()] }).targets).toEqual({ 0: "label" });
    expect(planFormErrors({ ...ok, targets: [{ ...emptyEffortRow(), label: "x", reps: "0" }] }).targets).toEqual({ 0: "reps" });
    expect(planFormErrors({ ...ok, targets: [{ ...emptyEffortRow(), label: "x", reps: "2.5" }] }).targets).toEqual({ 0: "reps" });
  });

  it("a time goes with an event and has to be readable", () => {
    const base = { ...emptyPlanForm("2026-11-10"), title: "T" };
    const row = { ...emptyEffortRow(), label: "x", time: "34.0" };
    expect(planFormErrors({ ...base, targets: [row] }).targets).toEqual({ 0: "time" }); // no event
    expect(planFormErrors({ ...base, targets: [{ ...row, eventKey: "500m" as const, time: "fast" }] }).targets).toEqual({ 0: "time" });
    expect(planFormErrors({ ...base, targets: [{ ...row, eventKey: "500m" as const }] }).targets).toEqual({});
  });

  it("builds the payload: times in ms, blanks as null, no start without an event", () => {
    const form = {
      ...emptyPlanForm("2026-11-10"),
      title: " Openers ",
      description: "  ",
      targets: [
        { label: "Standing", reps: "3", eventKey: "500m" as const, startType: "standing" as const, time: "34,5", gearId: "g1" },
        { label: "Tempo", reps: "4", eventKey: "" as const, startType: "standing" as const, time: "", gearId: "" },
      ],
    };
    expect(planPayload(form)).toEqual({
      planned_date: "2026-11-10",
      title: "Openers",
      description: null,
      targets: [
        { label: "Standing", reps: 3, event_key: "500m", start_type: "standing", target_time_ms: 34_500, gear_setup_id: "g1" },
        { label: "Tempo", reps: 4, event_key: null, start_type: null, target_time_ms: null, gear_setup_id: null },
      ],
    });
    expect(planPayload(emptyPlanForm(""))).toBeNull();
  });

  it("changing a block's event keeps a valid start and clears the rest when the event goes", () => {
    const row = { ...emptyEffortRow(), eventKey: "500m" as const, startType: "standing" as const, time: "34.0" };
    expect(withRowEvent(row, "1km")).toMatchObject({ eventKey: "1km", startType: "standing" });
    expect(withRowEvent(row, "f200")).toMatchObject({ eventKey: "f200", startType: "" }); // flying only
    expect(withRowEvent(row, "")).toMatchObject({ eventKey: "", startType: "", time: "" });
  });

  it("an edit starts from the saved plan", () => {
    const form = planFormFrom(
      plan({ description: "Easy", targets: [{ label: "Kilo", reps: 2, event_key: "1km", start_type: "standing", target_time_ms: 70_500, gear_setup_id: "g1" }] }),
      { seconds: () => "", lapTime: () => "1:10.500" },
    );
    expect(form).toMatchObject({ date: "2026-11-10", description: "Easy" });
    expect(form.targets).toEqual([{ label: "Kilo", reps: "2", eventKey: "1km", startType: "standing", time: "1:10.500", gearId: "g1" }]);
  });
});

describe("plan lists", () => {
  it("keeps the unanswered plans from the cut-off date, soonest first", () => {
    const plans = [
      plan({ id: "later", planned_date: "2026-11-20" }),
      plan({ id: "old", planned_date: "2026-10-01" }),
      plan({ id: "done", planned_date: "2026-11-11", status: "done" }),
      plan({ id: "soon", planned_date: "2026-11-05" }),
    ];
    expect(outstanding(plans, "2026-11-01").map((p) => p.id)).toEqual(["soon", "later"]);
  });

  it("offers the sessions near the date, nearest first", () => {
    const sessions = [{ event_date: "2026-11-13" }, { event_date: "2026-11-09" }, { event_date: "2026-11-10" }, { event_date: "2026-11-12" }];
    expect(linkCandidates(plan(), sessions).map((s) => s.event_date)).toEqual(["2026-11-10", "2026-11-09", "2026-11-12"]);
    expect(linkCandidates(plan(), sessions, 0).map((s) => s.event_date)).toEqual(["2026-11-10"]);
  });
});
