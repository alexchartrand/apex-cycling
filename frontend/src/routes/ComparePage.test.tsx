import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Effort } from "../features/training/types";
import { ComparePage } from "./ComparePage";

vi.mock("../features/athletes/useActiveAthlete", () => ({ useActiveAthlete: () => ({ data: { id: "a1" } }) }));

const effort = (first: string, laps: number[], over: Partial<Effort> = {}): Effort => ({
  index: 1,
  track_id: "t1",
  track_name: "Bromont",
  label: null,
  start_time: "2026-07-07T13:00:00Z",
  start_type: "flying",
  lap_ids: laps.map((_, i) => `${first}${i}`),
  completed_lap_count: laps.length,
  lap_times_ms: laps,
  total_time_ms: laps.reduce((sum, t) => sum + t, 0),
  best_lap_ms: Math.min(...laps),
  distance_m: laps.length * 250,
  avg_speed_kmh: 45,
  half_lap_splits: [],
  ...over,
});

const sessions = [
  { external_event_id: "e2", event_name: "Tuesday", event_date: "2026-07-14", track_names: ["Bromont"], lap_count: 4, rpe: null, tags: [], first_lap_at: null, last_lap_at: null },
  { external_event_id: "e1", event_name: "Last week", event_date: "2026-07-07", track_names: ["Bromont"], lap_count: 4, rpe: null, tags: [], first_lap_at: null, last_lap_at: null },
];
const efforts: Record<string, Effort[]> = {
  e1: [effort("a", [20_000, 20_000, 20_000, 20_000])],
  e2: [effort("b", [19_500, 19_500, 19_500, 19_500], { peak_speed_kmh: 63.4 })],
};

function renderPage(url: string) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <ComparePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ComparePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockImplementation((url: string) => {
      const match = /sessions\/([^/]+)\/efforts/.exec(url);
      return Promise.resolve(new Response(JSON.stringify(match ? (efforts[match[1]] ?? []) : sessions)));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("asks for a second effort until one is chosen", async () => {
    renderPage("/compare?a=e1");
    expect(await screen.findByText("Pick an effort on each side to compare them.")).toBeInTheDocument();
  });

  it("compares the two efforts the address names, picking the longest effort of each session", async () => {
    renderPage("/compare?a=e1&b=e2");
    const table = await screen.findByRole("table");
    const total = within(table).getByRole("row", { name: /^Time/ });
    expect(within(total).getByText("1:20.000")).toBeInTheDocument();
    expect(within(total).getByText("1:18.000")).toBeInTheDocument();
    expect(within(total).getByText("−2.000 s")).toBeInTheDocument(); // B is faster
    // Only B has a top speed.
    expect(within(table).getByRole("row", { name: /^Top speed/ })).toHaveTextContent("63.4 km/h");
  });

  it("refuses to compare an effort with itself", async () => {
    renderPage("/compare?a=e1&b=e1");
    expect(await screen.findByText("Both sides are the same effort. Pick a different one.")).toBeInTheDocument();
  });
});
