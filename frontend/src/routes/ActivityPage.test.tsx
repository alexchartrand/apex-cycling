import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/ui";
import type { Activity } from "../features/activities/types";
import { ActivityPage } from "./ActivityPage";

vi.mock("../features/athletes/useActiveAthlete", () => ({
  useActiveAthlete: () => ({ data: { id: "a1" } }),
  useViewingOther: () => ({ viewing: undefined, stopViewing: () => {} }),
}));

function Where() {
  const location = useLocation();
  return <p>{`${location.pathname}${location.search}`}</p>;
}

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/activities/r1"]}>
          <Routes>
            <Route path="/activities/:activityId" element={<ActivityPage />} />
            <Route path="/sessions/:eventId" element={<Where />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("ActivityPage", () => {
  const fetchMock = vi.fn();
  let eventId: string | null;

  beforeEach(() => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const path = new URL(url, "http://test").pathname;
      if (init?.method === "PATCH") return Promise.resolve(new Response(init.body as string));
      const body = path.endsWith("/activities/r1")
        ? ({ id: "r1", name: "Morning ride", source: "upload", start_time: "2026-04-04T09:00:00Z", elapsed_s: 3600, external_event_id: eventId, clock_offset_s: 0, activity_type: "cycling", activity_type_manual: false } as Activity)
        : path.endsWith("/session/suggestion")
          ? { external_event_id: null, confident: false }
          : path.endsWith("/analysis")
            ? { ftp_w: null, power_zones: null, hr_zones: null, power_curve: [] }
            : path.endsWith("/streams")
              ? { sample_count: 0, point_count: 0, time_s: [], power_w: null, heart_rate: null, cadence: null, speed_mps: null, distance_m: null, altitude_m: null }
              : [];
      return Promise.resolve(new Response(JSON.stringify(body)));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("sends a recording linked to a session to that session's Ride tab", async () => {
    eventId = "e1";
    renderPage();
    expect(await screen.findByText("/sessions/e1?tab=ride&recording=r1")).toBeInTheDocument();
  });

  it("shows a ride of its own on its page", async () => {
    eventId = null;
    renderPage();
    expect(await screen.findByRole("heading", { name: "Morning ride" })).toBeInTheDocument();
    expect(await screen.findByText("Not linked to a sqorz session.")).toBeInTheDocument();
  });

  it("renames and retypes the ride from the header", async () => {
    eventId = null;
    renderPage();
    expect(await screen.findByText("Cycling")).toBeInTheDocument(); // the type badge
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    const name = within(dialog).getByLabelText("Name");
    await userEvent.clear(name);
    await userEvent.type(name, "Trainer");
    await userEvent.selectOptions(within(dialog).getByLabelText(/^Type/), "indoor_cycling");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));

    await vi.waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PATCH");
      expect(JSON.parse((patch![1] as RequestInit).body as string)).toEqual({ name: "Trainer", activity_type: "indoor_cycling" });
    });
  });
});
