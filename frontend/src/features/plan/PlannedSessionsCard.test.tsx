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
  status: "planned",
  created_by_name: "Coach Cam",
  session: null,
  can_edit: false,
  can_mark: true,
  ...over,
});

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

  beforeEach(() => {
    plans = [plan()];
    sessions = [{ external_event_id: "evt1", event_name: "Tuesday night", event_date: day(2), track_names: [], lap_count: 10 }];
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/sessions")) return Promise.resolve(json(sessions));
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

  it("marks it done or skips it", async () => {
    sessions = [];
    renderCard();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Kilo openers/ }));
    expect(screen.getByText(/No session on this day/)).toBeInTheDocument();
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

  it("plans a session: title and date are sent with its efforts", async () => {
    plans = [];
    renderCard({ alwaysShow: true });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Plan a session" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(within(dialog).getByText("Give it a title")).toBeInTheDocument();

    await user.type(within(dialog).getByLabelText("Title"), "Openers");
    await user.click(within(dialog).getByRole("button", { name: "Add an effort" }));
    await user.type(within(dialog).getByLabelText("What"), "Starts");
    await user.selectOptions(within(dialog).getByLabelText("Event"), "500 m");
    await user.type(within(dialog).getByLabelText("Target"), "34,5");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const [url, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "POST")!;
    expect(url).toBe("/api/athletes/a1/planned-sessions");
    expect(JSON.parse(init.body)).toMatchObject({
      title: "Openers",
      description: null,
      targets: [{ label: "Starts", reps: 1, event_key: "500m", start_type: null, target_time_ms: 34_500, gear_setup_id: null }],
    });
  });
});
