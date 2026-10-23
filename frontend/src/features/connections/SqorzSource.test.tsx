import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../../components/ui";
import type { Insight } from "../insights/types";
import { SqorzSource } from "./SqorzSource";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

const assignment = {
  id: "as1",
  athlete_id: "a1",
  transponder_code: "LS-03407",
  start_date: "2026-01-01",
  end_date: null,
  notes: null,
  created_at: "2026-01-01T00:00:00Z",
};

const record: Insight = {
  key: "k1",
  kind: "personal_record",
  external_event_id: "e1",
  session_name: "Kilo day",
  event_date: "2026-10-21",
  track_id: "t1",
  track_name: "Bromont",
  event_key: "500m",
  start_type: "standing",
  time_ms: 47_535,
  previous_ms: 47_643,
  milestone_ms: null,
  lap_number: null,
  lap_count: null,
  cv_pct: null,
  effort_start_type: null,
  first_lap_id: null,
};

describe("SqorzSource", () => {
  const fetchMock = vi.fn();
  let sessions: { lap_count: number }[];
  let feed: Insight[];
  let feedCalls: number;

  beforeEach(() => {
    sessions = [];
    feed = [];
    feedCalls = 0;
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/transponder-assignments")) return Promise.resolve(json([assignment]));
      if (url.endsWith("/import") && init?.method === "POST") {
        feed = [record]; // the sync brought in a record
        return Promise.resolve(json({ id: "r1", status: "success", requested_at: "", completed_at: "", http_status: 200, error_message: null }));
      }
      if (url.endsWith("/sessions")) return Promise.resolve(json(sessions));
      if (url.includes("/insights")) {
        feedCalls += 1;
        return Promise.resolve(json(feed));
      }
      return Promise.resolve(json([]));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  function renderSource() {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
        <ToastProvider>
          <TooltipProvider>
            <SqorzSource athleteId="a1" />
          </TooltipProvider>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("says how many laps a sync found", async () => {
    sessions = [{ lap_count: 40 }, { lap_count: 2 }];
    renderSource();
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    expect(await screen.findByText("Found 42 laps in 2 sessions.")).toBeInTheDocument();
  });

  it("says so when there are no laps yet", async () => {
    renderSource();
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    expect(await screen.findByText(/No laps yet/)).toBeInTheDocument();
  });

  it("announces the records a sync brought in, and only those", async () => {
    sessions = [{ lap_count: 10 }];
    renderSource();
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    expect(await screen.findByText("1 new highlight")).toBeInTheDocument();
    expect(await screen.findByText("New record · 500 m")).toBeInTheDocument();
    expect(feedCalls).toBeGreaterThan(1); // before and after the sync
  });

  it("explains where to find the transponder code", async () => {
    renderSource();
    await userEvent.click(await screen.findByText("Where do I find the code?"));
    expect(screen.getByText(/printed on the transponder itself/)).toBeVisible();
  });
});
