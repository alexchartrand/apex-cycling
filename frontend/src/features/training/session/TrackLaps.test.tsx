import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../../../components/ui";
import type { LapDetail, SegmentDetail, TrackSessionDetail, TrackSummary } from "../types";
import { TrackLaps } from "./TrackLaps";

const seg = (loopId: string, name: string, index: number, ms: number): SegmentDetail => ({
  sequence_index: index,
  loop_id: loopId,
  loop_name: name,
  time_ms: ms,
});

const segments = [seg("curve", "Courbe 1", 0, 5000), seg("p2", "Poursuite 2", 1, 7000), seg("p1", "Poursuite 1", 2, 14000), seg("fin", "Finish", 3, 1500)];

const lap = (id: string, total: number, excluded = false): LapDetail => ({
  lap_id: id,
  start_time: "2026-07-07T13:43:57.134Z",
  class_code: null,
  start_number: null,
  whole_lap_time_ms: total,
  excluded,
  label: null,
  segments,
  views: [],
});

const track: TrackSessionDetail = {
  track_id: "t1",
  track_name: "Tour complet",
  laps: [lap("l1", 27500), lap("l2", 28000, true)],
};

const meta: TrackSummary = {
  id: "t1",
  name: "Tour complet",
  length_m: 250,
  indoor: true,
  elevation_m: null,
  default_temp_c: null,
  can_edit: false,
  views: [],
  loops: [
    { id: "curve", name: "Courbe 1", distance_m: 60, hidden: true },
    { id: "p2", name: "Poursuite 2", distance_m: 110, hidden: false },
    { id: "p1", name: "Poursuite 1", distance_m: 235, hidden: false },
    { id: "fin", name: "Finish", distance_m: 250, hidden: false },
  ],
};

function renderLaps() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <TrackLaps athleteId="a1" sessionTitle="Session" track={track} meta={meta} />
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("TrackLaps", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("has a split column per visible checkpoint and none for hidden ones", () => {
    renderLaps();
    const table = screen.getByRole("table", { name: "Laps on Tour complet" });
    const headers = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual(expect.arrayContaining(["Poursuite 2 (s)", "Poursuite 1 (s)", "Finish (s)"]));
    expect(headers.join("|")).not.toContain("Courbe");
  });

  it("shows speed from the track length and marks excluded laps", () => {
    renderLaps();
    const table = screen.getByRole("table", { name: "Laps on Tour complet" });
    const rows = within(table).getAllByRole("row");
    expect(within(rows[1]).getByText("32.7")).toBeInTheDocument(); // 250 m in 27.5 s
    expect(within(rows[2]).getByText("Excluded")).toBeInTheDocument();
  });

  it("highlights the split column of the checkpoint picked on the diagram", async () => {
    renderLaps();
    const user = userEvent.setup();
    const table = screen.getByRole("table", { name: "Laps on Tour complet" });
    const header = () => within(table).getByRole("columnheader", { name: /Poursuite 1/ });
    expect(header()).not.toHaveClass("data-table__col--highlight");

    await user.click(screen.getByRole("button", { name: /Poursuite 1, /i }));
    expect(header()).toHaveClass("data-table__col--highlight");

    await user.click(screen.getByRole("button", { name: /Poursuite 1, /i })); // again: deselect
    expect(header()).not.toHaveClass("data-table__col--highlight");
  });

  it("excludes and re-includes a lap with a PATCH", async () => {
    renderLaps();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Exclude lap 1" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    let [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/athletes/a1/laps/l1");
    expect(JSON.parse(init.body)).toEqual({ excluded: true });

    fetchMock.mockClear();
    await user.click(screen.getByRole("button", { name: "Include lap 2" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/athletes/a1/laps/l2");
    expect(JSON.parse(init.body)).toEqual({ excluded: false });
  });
});
