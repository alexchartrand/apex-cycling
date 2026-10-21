import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../../components/ui";
import { GoalsCard } from "./GoalsCard";
import type { Goal } from "./types";

const base: Goal = {
  id: "g1",
  event_key: "1km",
  start_type: "standing",
  track_id: null,
  track_name: null,
  target_time_ms: 70_000,
  target_date: "2099-01-01",
  notes: "Nationals",
  baseline_ms: 80_000,
  created_at: "2026-10-01T00:00:00Z",
  best: { time_ms: 75_000, achieved_on: "2026-09-01", place: "Bromont", track_id: "t1" },
  gap_ms: 5_000,
  achieved: false,
  progress: 0.5,
  days_left: 40,
  prediction: {
    time_ms: 68_500,
    power_w: 512,
    power_duration_s: 60,
    power_on: "2026-09-12T10:00:00Z",
    cda_m2: 0.231,
    cda_label: "Hoods",
    rider_kg: 74,
  },
  prediction_problem: null,
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function renderCard() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter>
            <GoalsCard athleteId="a1" />
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("GoalsCard", () => {
  const fetchMock = vi.fn();
  let goals: Goal[];

  beforeEach(() => {
    goals = [base];
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/tracks")) return Promise.resolve(json([{ id: "t1", name: "Bromont" }]));
      if (init?.method === "POST") return Promise.resolve(json(base, 201));
      return Promise.resolve(json(goals));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("shows the best against the target, the days left and the prediction with its basis", async () => {
    renderCard();
    expect(await screen.findByText("1 km · Standing start")).toBeInTheDocument();
    expect(screen.getByText("Any track")).toBeInTheDocument();
    expect(screen.getByText("1:10.000")).toBeInTheDocument(); // target
    expect(screen.getByText("1:15.000")).toBeInTheDocument(); // best
    expect(screen.getByText("+5.000 s")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0.5");
    expect(screen.getByText("40 days left")).toBeInTheDocument();
    expect(screen.getByText(/Predicted 1:08.500/)).toBeInTheDocument();
    expect(screen.getByText(/beats the target by 1.500 s/)).toBeInTheDocument();
    expect(screen.getByText(/512 W over 1:00/)).toBeInTheDocument();
    expect(screen.getByText("Nationals")).toBeInTheDocument();
  });

  it("marks a reached goal and says what a missing prediction needs", async () => {
    goals = [
      { ...base, best: { ...base.best!, time_ms: 69_000 }, gap_ms: -1_000, achieved: true, progress: 1, prediction: null, prediction_problem: "no_cda" },
    ];
    renderCard();
    expect((await screen.findAllByText("Reached")).length).toBeGreaterThan(0);
    expect(screen.getByText(/save an aero test/)).toBeInTheDocument();
    expect(screen.queryByText(/Predicted/)).not.toBeInTheDocument();
  });

  it("explains an empty list", async () => {
    goals = [];
    renderCard();
    expect(await screen.findByText(/Set a target time/)).toBeInTheDocument();
  });

  it("adds a goal: the time is read into ms and the track and notes go as null", async () => {
    goals = [];
    renderCard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Add a goal" }));
    const dialog = screen.getByRole("dialog");

    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(within(dialog).getByText(/Enter a time/)).toBeInTheDocument(); // nothing was sent
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);

    await user.type(within(dialog).getByLabelText("Target time"), "1:10,5");
    await user.type(within(dialog).getByLabelText("Date to reach it by"), "2099-02-03");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const [url, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "POST")!;
    expect(url).toBe("/api/athletes/a1/goals");
    expect(JSON.parse(init.body)).toEqual({
      event_key: "1km",
      start_type: "standing",
      target_time_ms: 70_500,
      target_date: "2099-02-03",
      track_id: null,
      notes: null,
    });
  });

  it("an edit can't change the event", async () => {
    renderCard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Edit goal/ }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("Event")).toBeDisabled();
    expect(within(dialog).getByLabelText("Target time")).toHaveValue("1:10.000");
  });
});
