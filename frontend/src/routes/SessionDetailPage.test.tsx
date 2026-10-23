import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/ui";
import type { Activity } from "../features/activities/types";
import type { LinkedActivity, SessionDetail } from "../features/training/types";
import { SessionDetailPage } from "./SessionDetailPage";

vi.mock("../features/athletes/useActiveAthlete", () => ({
  useActiveAthlete: () => ({ data: { id: "a1" } }),
  useViewingOther: () => ({ viewing: undefined, stopViewing: () => {} }),
}));

const linked = (id: string, name: string): LinkedActivity => ({
  id, name, start_time: "2026-04-04T17:55:00Z", elapsed_s: 3600, clock_offset_s: 0, has_power: true, has_heart_rate: true, has_cadence: false,
});

function detail(activities: LinkedActivity[]): SessionDetail {
  return {
    external_event_id: "e1", event_name: "Saturday", original_name: "Saturday", title_override: null, event_date: "2026-04-04",
    notes: null, rpe: null, tags: [], tracks: [{ track_id: "t1", track_name: "Bromont", laps: [] }], activities,
  } as SessionDetail;
}

function activity(id: string, name: string): Activity {
  return {
    id, athlete_id: "a1", source: "upload", name, sport: "cycling", start_time: "2026-04-04T17:55:00Z", elapsed_s: 3600, moving_s: 3500,
    distance_m: 30_000, elevation_gain_m: 0, has_power: true, has_heart_rate: true, has_cadence: false, avg_power_w: 210, max_power_w: 900,
    normalized_power_w: 240, tss: 60, avg_heart_rate: 150, max_heart_rate: 185, avg_cadence: null, avg_speed_mps: 9, notes: null, rpe: null,
    file_format: "fit", created_at: "2026-04-04T20:00:00Z", external_event_id: "e1", external_url: null, clock_offset_s: 0, session_link_manual: false,
  } as Activity;
}

function renderPage(url: string) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route path="/sessions/:eventId" element={<SessionDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("SessionDetailPage — Ride tab", () => {
  const fetchMock = vi.fn();
  let session: SessionDetail;

  beforeEach(() => {
    fetchMock.mockImplementation((url: string) => {
      const path = new URL(url, "http://test").pathname;
      let body: unknown = [];
      if (path.endsWith("/athletes/a1/sessions/e1")) body = session;
      const recording = /\/activities\/([^/]+)(\/\w+)?$/.exec(path);
      if (recording && !recording[2]) body = activity(recording[1], recording[1] === "r1" ? "Garmin" : "Wahoo");
      if (recording?.[2] === "/analysis")
        body = { ftp_w: 300, weight_kg: 70, max_hr: null, intensity_factor: 0.8, variability_index: 1.1, avg_power_w_per_kg: 3, normalized_power_w_per_kg: 3.4, work_kj: 750, power_zones: null, hr_zones: null, power_curve: [] };
      if (recording?.[2] === "/streams")
        body = { sample_count: 2, point_count: 2, time_s: [0, 1], power_w: [200, 220], heart_rate: null, cadence: null, speed_mps: null, distance_m: null, altitude_m: null };
      return Promise.resolve(new Response(JSON.stringify(body)));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("has no Ride tab without a recording, and falls back to the overview", async () => {
    session = detail([]);
    renderPage("/sessions/e1?tab=ride");
    expect(await screen.findByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Ride" })).not.toBeInTheDocument();
  });

  it("shows the linked recording on the Ride tab", async () => {
    session = detail([linked("r1", "Garmin")]);
    renderPage("/sessions/e1?tab=ride");
    expect(await screen.findByRole("tab", { name: "Ride", selected: true })).toBeInTheDocument();
    expect(await screen.findByText("Linked to …")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete activity" })).toBeInTheDocument();
    // A single recording needs no picker.
    expect(screen.queryByRole("radiogroup", { name: "Recording" })).not.toBeInTheDocument();
  });

  it("shows the recording's streams on the overview, and the rest of it on the Ride tab", async () => {
    session = detail([linked("r1", "Garmin")]);
    renderPage("/sessions/e1");
    expect(await screen.findByRole("heading", { name: "Ride" })).toBeInTheDocument();
    expect(screen.getByText("Power (W)")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Ride" }));
    expect(await screen.findByText("Linked to …")).toBeInTheDocument();
    expect(screen.queryByText("Power (W)")).not.toBeInTheDocument();
  });

  it("picks between several recordings, starting from the one the address names", async () => {
    session = detail([linked("r1", "Garmin"), linked("r2", "Wahoo")]);
    renderPage("/sessions/e1?tab=ride&recording=r2");
    expect(await screen.findByRole("radio", { name: "Wahoo", checked: true })).toBeInTheDocument();
    await screen.findByText("Linked to …");
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/activities/r2"))).toBe(true);

    await userEvent.click(screen.getByRole("radio", { name: "Garmin" }));
    expect(await screen.findByRole("radio", { name: "Garmin", checked: true })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/activities/r1"))).toBe(true);
  });
});
