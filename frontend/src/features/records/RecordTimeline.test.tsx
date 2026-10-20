import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RecordTimeline } from "./RecordTimeline";
import type { RecordEntry } from "./types";

const history: RecordEntry[] = [
  { place: "Tour complet", track_id: "t1", event_key: "500m", start_type: "standing", time_ms: 40_000, achieved_on: "2026-03-28", source: "sqorz", is_competition: false, external_event_id: "e1", lap_id: "l1", manual_result_id: null },
  { place: "Tour complet", track_id: "t1", event_key: "500m", start_type: "standing", time_ms: 38_500, achieved_on: "2026-04-04", source: "sqorz", is_competition: false, external_event_id: "e2", lap_id: "l2", manual_result_id: null },
  { place: "Tour complet", track_id: "t1", event_key: "500m", start_type: "standing", time_ms: 37_900, achieved_on: "2026-09-01", source: "manual", is_competition: true, external_event_id: null, lap_id: null, manual_result_id: "m1" },
];

function renderTimeline(selection: Parameters<typeof RecordTimeline>[0]["selection"]) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <RecordTimeline athleteId="a1" selection={selection} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RecordTimeline", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(history), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("asks for a track record's history by track id", async () => {
    renderTimeline({ track_id: "t1", place: "Tour complet", event_key: "500m", start_type: "standing" });
    await screen.findByRole("table");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/athletes/a1/records/history?event_key=500m&start_type=standing&track_id=t1");
  });

  it("asks for a manual venue's history by venue text", async () => {
    renderTimeline({ track_id: null, place: "Mont-Royal", event_key: "1km", start_type: "flying" });
    await screen.findByRole("table");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/athletes/a1/records/history?event_key=1km&start_type=flying&venue=Mont-Royal");
  });

  it("lists the improvements newest first with their gain, and where each came from", async () => {
    renderTimeline({ track_id: "t1", place: "Tour complet", event_key: "500m", start_type: "standing" });
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").slice(1); // skip the header
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("37.900 s")).toBeInTheDocument();
    expect(within(rows[0]).getByText("−0.600 s")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Added by you")).toBeInTheDocument();
    expect(within(rows[1]).getByText("−1.500 s")).toBeInTheDocument();
    expect(within(rows[1]).getByRole("link", { name: "Session" })).toHaveAttribute("href", "/sessions/e2");
    expect(within(rows[2]).getByText("First result")).toBeInTheDocument();
  });

  it("invites you to pick a record when none is selected", () => {
    renderTimeline(null);
    expect(screen.getByText("Select a record on the board.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
