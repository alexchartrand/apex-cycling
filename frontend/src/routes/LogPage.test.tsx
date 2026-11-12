import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LogPage } from "./LogPage";

vi.mock("../features/athletes/useActiveAthlete", () => ({ useActiveAthlete: () => ({ data: { id: "a1" } }) }));

const session = (id: string, date: string) => ({
  external_event_id: id, event_name: `Session ${id}`, event_date: date, track_names: [], lap_count: 3,
  rpe: null, tags: [], is_race: false, first_lap_at: `${date}T18:00:00Z`, last_lap_at: null,
});  // prettier-ignore
const activity = (id: string, start: string) => ({
  id, name: `Ride ${id}`, start_time: start, source: "upload", elapsed_s: 3600, distance_m: null, avg_speed_mps: null,
  has_power: false, has_heart_rate: false, external_event_id: null,
});  // prettier-ignore

// Newest first, with a gap between June 2025 and March 2026.
const SESSIONS = [session("s3", "2026-05-20"), session("s2", "2026-03-02"), session("s1", "2025-06-10")];
const ACTIVITIES = [activity("r2", "2026-04-10T12:00:00Z"), activity("r1", "2025-05-05T12:00:00Z")];

/** A tiny backend honouring the bounds, as the real one does. */
function respond(url: string): unknown {
  const parsed = new URL(url, "http://test");
  const q = parsed.searchParams;
  if (parsed.pathname.endsWith("/sessions")) {
    const rows = SESSIONS.filter((s) => (!q.get("from") || s.event_date >= q.get("from")!) && (!q.get("to") || s.event_date <= q.get("to")!));
    return q.get("limit") ? rows.slice(0, Number(q.get("limit"))) : rows;
  }
  if (parsed.pathname.endsWith("/activities")) {
    const rows = ACTIVITIES.filter((a) => (!q.get("start") || a.start_time >= q.get("start")!) && (!q.get("end") || a.start_time < q.get("end")!));
    const offset = Number(q.get("offset") ?? 0);
    return rows.slice(offset, offset + Number(q.get("limit")));
  }
  return [];
}

function renderPage(url = "/log") {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <LogPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LogPage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockImplementation((url: string) => Promise.resolve(new Response(JSON.stringify(respond(url)))));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  const sessionCalls = () => fetchMock.mock.calls.map(([url]) => url as string).filter((url) => url.includes("/sessions"));

  it("lists the newest months a page at a time, skipping empty stretches", async () => {
    renderPage();
    expect(await screen.findByText("Session s3")).toBeInTheDocument();
    expect(screen.getByText("Ride r2")).toBeInTheDocument();
    expect(screen.getByText("Session s2")).toBeInTheDocument();
    expect(screen.queryByText("Session s1")).not.toBeInTheDocument();
    // Never the whole history.
    expect(sessionCalls().every((url) => /[?&](from|to|limit)=/.test(url))).toBe(true);

    await userEvent.click(await screen.findByRole("button", { name: "Load earlier months" }));
    expect(await screen.findByText("Session s1")).toBeInTheDocument();
    expect(screen.getByText("Ride r1")).toBeInTheDocument();
    // June and May 2025: nothing older, so no more button.
    await vi.waitFor(() => expect(screen.queryByRole("button", { name: "Load earlier months" })).not.toBeInTheDocument());
  });

  it("asks the calendar only for the days of its grid", async () => {
    renderPage("/log?view=calendar&month=2026-03");
    expect(await screen.findByText("Session s2")).toBeInTheDocument();
    expect(screen.queryByText("Session s3")).not.toBeInTheDocument();
    // March 2026 starts on a Sunday: the grid runs from Monday 23 February to Sunday 5 April.
    expect(sessionCalls()).toContain("/api/athletes/a1/sessions?from=2026-02-23&to=2026-04-05");
  });
});
