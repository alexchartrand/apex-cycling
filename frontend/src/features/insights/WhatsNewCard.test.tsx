import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InsightRow } from "./InsightRow";
import type { Insight } from "./types";
import { WhatsNewCard } from "./WhatsNewCard";

const record: Insight = {
  key: "a",
  kind: "personal_record",
  external_event_id: "s1",
  session_name: "Tuesday kilo",
  event_date: "2026-04-04",
  track_id: "t1",
  track_name: "Bromont",
  event_key: "500m",
  start_type: "standing",
  time_ms: 47_535,
  previous_ms: 51_434,
  milestone_ms: 48_000,
  lap_number: null,
  lap_count: null,
  cv_pct: null,
  effort_start_type: null,
  first_lap_id: null,
};

afterEach(() => vi.restoreAllMocks());

describe("InsightRow", () => {
  it("names the event, the time, the gain and the round time that was broken", () => {
    render(<InsightRow insight={record} />);
    expect(screen.getByText("New record · 500 m")).toBeInTheDocument();
    const detail = screen.getByText(/Standing start · 47\.535 s, 3\.899 s faster than 51\.434 s/);
    expect(detail).toHaveTextContent("first time under 48.000 s");
  });

  it("describes the pacing headline", () => {
    render(<InsightRow insight={{ ...record, kind: "most_consistent", event_key: null, start_type: null, effort_start_type: "flying", lap_count: 8, cv_pct: 0.84 }} />);
    expect(screen.getByText("Most consistent effort of the season")).toBeInTheDocument();
    expect(screen.getByText(/8 laps, lap times within 0\.8 % of each other/)).toBeInTheDocument();
  });
});

describe("WhatsNewCard", () => {
  function renderCard(feed: Insight[]) {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(feed), { status: 200 }));
    return render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <WhatsNewCard athleteId="a1" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("lists the headlines under a link to their session", async () => {
    renderCard([record, { ...record, key: "b", kind: "season_best", event_key: "1km" }]);
    const link = await screen.findByRole("link", { name: /Tuesday kilo/ });
    expect(link).toHaveAttribute("href", "/sessions/s1");
    expect(screen.getByText("Season best · 1 km")).toBeInTheDocument();
  });

  it("renders nothing without headlines", async () => {
    const { container } = renderCard([]);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(container).toBeEmptyDOMElement();
  });
});
