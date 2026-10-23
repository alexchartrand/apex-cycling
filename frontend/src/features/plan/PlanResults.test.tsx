import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlanResults } from "./PlanResults";
import type { PlanComparison, RepResult } from "./types";

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
};

function renderResults() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <PlanResults athleteId="a1" planId="p1" eventId="evt1" />
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
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't compare the plan with the session.");
  });
});
