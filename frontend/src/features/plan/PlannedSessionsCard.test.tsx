import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../../components/ui";
import { localIsoDate } from "../../i18n/format";
import { PlannedSessionsCard } from "./PlannedSessionsCard";
import type { PlannedSession } from "./types";

const day = (offset: number) => {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return localIsoDate(date);
};

const plan = (over: Partial<PlannedSession> = {}): PlannedSession => ({
  id: "p1",
  planned_date: day(2),
  title: "Kilo openers",
  description: "Full recovery",
  targets: [
    { label: "Standing start", reps: 3, event_key: "500m", start_type: "standing", target_time_ms: 34_000, gear_setup_id: "g1", gear_label: "Track bike · 50×15" },
    { label: "Tempo", reps: 1, event_key: null, start_type: null, target_time_ms: null, gear_setup_id: null },
  ],
  workout: null,
  workout_estimate: null,
  workout_gears: [],
  source_workout_id: null,
  status: "planned",
  created_by_name: "Coach Cam",
  session: null,
  activity: null,
  can_edit: false,
  can_mark: true,
  intervals: null,
  ...over,
});

const STEP = { kind: "work", label: "Flying", notes: null, duration_s: null, distance_m: null, laps: null, power: null, cadence: null, rpe: null, event_key: "f200", start_type: "flying", target_time_ms: 11_500, gear: null };
const LIBRARY_WORKOUT = {
  id: "w1",
  source: "preset",
  name: "Sprint openers",
  description: "Short and sharp",
  tags: [],
  is_track: true,
  duration_s: 1200,
  tss: 20,
  owner_name: null,
  can_edit: false,
  created_at: null,
  steps: [{ type: "repeat", count: 3, steps: [STEP] }],
  estimate: { duration_s: 1200, tss: 20, unrated_s: 0, open_steps: 0, segments: [] },
};

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

function renderCard(props: { alwaysShow?: boolean } = {}) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter>
            <PlannedSessionsCard athleteId="a1" {...props} />
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("PlannedSessionsCard", () => {
  const fetchMock = vi.fn();
  let plans: PlannedSession[];
  let sessions: { external_event_id: string; event_name: string; event_date: string; track_names: string[]; lap_count: number }[];
  let activities: { id: string; name: string | null; start_time: string; external_event_id: string | null }[];

  beforeEach(() => {
    plans = [plan()];
    sessions = [{ external_event_id: "evt1", event_name: "Tuesday night", event_date: day(2), track_names: [], lap_count: 10 }];
    activities = [];
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes("/sessions?")) {
        // Only the days around the plan are asked for.
        const query = new URL(url, "http://test").searchParams;
        return Promise.resolve(json(sessions.filter((s) => s.event_date >= query.get("from")! && s.event_date <= query.get("to")!)));
      }
      if (url.includes("/activities")) return Promise.resolve(json(activities));
      if (url === "/api/workouts/estimate") return Promise.resolve(json({ duration_s: 1200, tss: 20, unrated_s: 0, open_steps: 0, segments: [] }));
      if (url === "/api/workouts/w1") return Promise.resolve(json(LIBRARY_WORKOUT));
      if (url.startsWith("/api/workouts")) return Promise.resolve(json([{ ...LIBRARY_WORKOUT, steps: undefined, estimate: undefined }]));
      if (init?.method === "PUT" || init?.method === "PATCH") return Promise.resolve(json(plan({ status: "done" })));
      return Promise.resolve(json(plans));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists what is waiting and opens the plan with its efforts", async () => {
    renderCard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Kilo openers/ }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Full recovery")).toBeInTheDocument();
    expect(within(dialog).getByText("3 × Standing start — 500 m, 34.000 s, Track bike · 50×15")).toBeInTheDocument();
    expect(within(dialog).getByText("Tempo")).toBeInTheDocument();
    expect(within(dialog).getByText(/by Coach Cam/)).toBeInTheDocument();
  });

  it("shows a scheduled workout, its gears in the athlete's words and a way back to the library", async () => {
    plans = [
      plan({
        targets: [],
        workout: [{ type: "repeat", count: 3, steps: [{ ...STEP, gear: { chainring_teeth: 50, cog_teeth: 15 } }] }] as PlannedSession["workout"],
        workout_estimate: { duration_s: 1500, tss: 30, unrated_s: 0, open_steps: 0, segments: [] },
        workout_gears: [{ chainring_teeth: 50, cog_teeth: 15, gear_setup_id: "g1", label: "Track bike · 50×15" }],
        source_workout_id: "w1",
      }),
    ];
    renderCard();
    const user = userEvent.setup();
    expect(await screen.findByText("25 min")).toBeInTheDocument(); // the list shows the duration
    await user.click(screen.getByRole("button", { name: /Kilo openers/ }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Flying")).toBeInTheDocument();
    expect(within(dialog).getByText(/Track bike · 50×15/)).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: /Open the library workout/ })).toHaveAttribute("href", "/workouts/w1");
  });

  it("links the session ridden near the date, which is picked for you", async () => {
    renderCard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Kilo openers/ }));
    await user.click(await screen.findByRole("button", { name: "Link it" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(true));
    const [url, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "PUT")!;
    expect(url).toBe("/api/athletes/a1/planned-sessions/p1/session");
    expect(JSON.parse(init.body)).toEqual({ external_event_id: "evt1" });
  });

  it("links a recording when the ride had no sqorz timing", async () => {
    sessions = [];
    activities = [
      { id: "act1", name: "Trainer intervals", start_time: `${day(2)}T12:00:00Z`, external_event_id: null },
      { id: "act2", name: "At the track", start_time: `${day(2)}T19:00:00Z`, external_event_id: "evt9" },
    ];
    renderCard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Kilo openers/ }));
    const select = await screen.findByLabelText("What you rode");
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual([expect.stringContaining("Recording: Trainer intervals")]);
    await user.click(screen.getByRole("button", { name: "Link it" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(true));
    const [url, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "PUT")!;
    expect(url).toBe("/api/athletes/a1/planned-sessions/p1/activity");
    expect(JSON.parse(init.body)).toEqual({ activity_id: "act1" });
  });

  it("marks it done or skips it", async () => {
    sessions = [];
    renderCard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Kilo openers/ }));
    expect(screen.getByText(/Nothing ridden on this day/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Skip it" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(true));
    const [url, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "PATCH")!;
    expect(url).toBe("/api/athletes/a1/planned-sessions/p1");
    expect(JSON.parse(init.body)).toEqual({ status: "skipped" });
  });

  it("gives a coach no way to answer for the athlete, only to edit their own plan", async () => {
    plans = [plan({ can_mark: false, can_edit: true })];
    renderCard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Kilo openers/ }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).queryByRole("button", { name: "Mark as done" })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Link it" })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("flags an unanswered plan that is past, and drops answered ones", async () => {
    plans = [plan({ id: "late", title: "Missed one", planned_date: day(-3) }), plan({ id: "ok", title: "Already done", status: "done" })];
    renderCard();
    expect(await screen.findByText("Missed one")).toBeInTheDocument();
    expect(screen.getByText("Past due")).toBeInTheDocument();
    expect(screen.queryByText("Already done")).not.toBeInTheDocument();
  });

  it("hides itself when nothing waits, unless asked to stay", async () => {
    plans = [];
    renderCard();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText("Planned sessions")).not.toBeInTheDocument());
  });

  it("plans a session from a library workout: the plan gets its own copy", async () => {
    plans = [];
    renderCard({ alwaysShow: true });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Plan a session" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(within(dialog).getByText("Give it a title")).toBeInTheDocument();
    expect(within(dialog).getByText("Choose a workout")).toBeInTheDocument();
    // Workouts are only chosen here, never built or edited.
    expect(within(dialog).queryByRole("button", { name: /build the steps|add a step/i })).toBeNull();

    await within(dialog).findByRole("option", { name: "Sprint openers" });
    await user.selectOptions(within(dialog).getByLabelText("Workout"), "w1");
    await waitFor(() => expect(within(dialog).getByLabelText("Title")).toHaveValue("Sprint openers"));
    expect(within(dialog).queryByRole("textbox", { name: /label/i })).toBeNull();
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([u, init]) => u.includes("planned-sessions") && init?.method === "POST")).toBe(true));
    const [url, init] = fetchMock.mock.calls.find(([u, i]) => u.includes("planned-sessions") && i?.method === "POST")!;
    expect(url).toBe("/api/athletes/a1/planned-sessions");
    expect(JSON.parse(init.body)).toMatchObject({
      title: "Sprint openers",
      description: "Short and sharp",
      targets: [],
      source_workout_id: "w1",
      workout: [{ type: "repeat", count: 3, steps: [{ label: "Flying", event_key: "f200", start_type: "flying", target_time_ms: 11_500 }] }],
    });
  });
});
