import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlanResults } from "./PlanResults";
import type { PlanComparison, RepResult, StepResult } from "./types";

const rep = (over: Partial<RepResult>): RepResult => ({
  target_index: 0,
  rep: 1,
  label: "Kilos",
  event_key: "1km",
  target_time_ms: 75_000,
  status: "hit",
  effort_index: 1,
  start_type: "flying",
  time_ms: 70_000,
  delta_ms: -5_000,
  ...over,
});

const comparison: PlanComparison = {
  reps: [
    rep({}),
    rep({ rep: 2, status: "miss", time_ms: 80_000, delta_ms: 5_000, effort_index: 2 }),
    rep({ target_index: 1, rep: 1, label: "Jog", event_key: null, target_time_ms: null, status: "free", effort_index: null, start_type: null, time_ms: null, delta_ms: null }),
    rep({ target_index: 2, rep: 1, label: "Start", event_key: "500m", status: "not_ridden", effort_index: null, start_type: null, time_ms: null, delta_ms: null }),
  ],
  measured: 3,
  hits: 1,
  recording: null,
  steps: [],
  power_measured: 0,
  power_hits: 0,
};

const step = (over: Partial<StepResult>): StepResult => ({
  step_index: 1,
  kind: "work",
  label: "VO2",
  power: { unit: "ftp_pct", low: 105, high: null },
  cadence: null,
  power_low_w: 262.5,
  power_high_w: 262.5,
  start_s: 690,
  end_s: 870,
  avg_power_w: 265,
  avg_cadence: null,
  power_status: "hit",
  cadence_status: null,
  ...over,
});

const powerComparison: PlanComparison = {
  reps: [],
  measured: 0,
  hits: 0,
  recording: { id: "act1", name: "Trainer ride", start_time: "2026-06-20T09:00:00Z" },
  steps: [
    step({ step_index: 0, kind: "warmup", label: null, power: { unit: "watts", low: 130, high: 150 }, power_low_w: 130, power_high_w: 150, start_s: 90, avg_power_w: 140 }),
    step({}),
    step({ step_index: 5, avg_power_w: 230, power_status: "under", cadence: { low: 90, high: 100 }, avg_cadence: 104, cadence_status: "over" }),
    step({ step_index: 7, power: { unit: "ftp_pct", low: 90, high: null }, power_low_w: null, power_high_w: null, start_s: null, avg_power_w: null, power_status: "unmeasured" }),
  ],
  power_measured: 3,
  power_hits: 2,
};

function renderResults(eventId: string | null = "evt1") {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <PlanResults athleteId="a1" planId="p1" eventId={eventId} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PlanResults", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("shows hit or miss per rep with the gap to the target", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(comparison)));
    renderResults();

    expect(await screen.findByText("1 of 3 targets made.")).toBeInTheDocument();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(4);
    expect(within(rows[0]).getByText("Made it")).toBeInTheDocument();
    expect(within(rows[0]).getByText(/−5\.00 s/)).toBeInTheDocument();
    expect(within(rows[1]).getByText("Missed")).toBeInTheDocument();
    expect(within(rows[1]).getByText(/\+5\.00 s/)).toBeInTheDocument();
    expect(within(rows[2]).getByText("Not measured")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Not ridden")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toContain("/athletes/a1/planned-sessions/p1/comparison");
  });

  it("says so when the comparison can't be loaded", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 500 }));
    renderResults();
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't compare the plan with what was ridden.");
  });

  it("shows each power step against the recording", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(powerComparison)));
    renderResults(null);

    expect(await screen.findByText(/2 of 3 power targets held/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Trainer ride" })).toHaveAttribute("href", "/activities/act1");
    const rows = within(screen.getByRole("list", { name: "Power and cadence steps" })).getAllByRole("listitem");
    expect(rows).toHaveLength(4);
    expect(rows[0]).toHaveTextContent("Warm-up");
    expect(rows[0]).toHaveTextContent("1:30");
    expect(rows[0]).toHaveTextContent("140 W / 130–150 W");
    expect(within(rows[1]).getByText("On target")).toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("265 W / 263 W");
    expect(within(rows[2]).getByText("Under")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Cadence: Over")).toBeInTheDocument();
    expect(rows[2]).toHaveTextContent("104 rpm / 90–100 rpm");
    expect(rows[3]).toHaveTextContent("– / 90 % FTP");
    expect(within(rows[3]).getByText("Not measured")).toBeInTheDocument();
  });

  it("asks for a recording when there's none to read the power steps from", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ...powerComparison, recording: null, steps: [] })));
    renderResults(null);
    expect(await screen.findByText(/No recording to read the power steps from/)).toBeInTheDocument();
  });
});
