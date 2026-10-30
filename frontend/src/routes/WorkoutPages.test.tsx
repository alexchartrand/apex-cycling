import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../components/ui";
import type { Workout, WorkoutEstimate, WorkoutSummary } from "../features/workouts/types";
import { WorkoutEditPage } from "./WorkoutEditPage";
import { WorkoutPage } from "./WorkoutPage";
import { WorkoutsPage } from "./WorkoutsPage";

const estimate: WorkoutEstimate = {
  duration_s: 1500,
  tss: 30,
  unrated_s: 0,
  open_steps: 0,
  segments: [
    { start_s: 0, duration_s: 600, kind: "warmup", label: null, intensity: 0.6, power_low: null, power_high: null, is_track: false },
    { start_s: 600, duration_s: 900, kind: "work", label: "Tempo", intensity: 0.85, power_low: 0.8, power_high: 0.9, is_track: false },
  ],
};

const summary: WorkoutSummary = {
  id: "w1",
  source: "preset",
  name: "Flying 200s",
  description: "Top speed",
  tags: ["sprint", "track"],
  is_track: true,
  duration_s: 3600,
  tss: 55,
  owner_name: null,
  can_edit: false,
  created_at: null,
};

const preset: Workout = {
  ...summary,
  steps: [
    { kind: "warmup", label: null, notes: null, duration_s: 600, distance_m: null, laps: null, power: null, cadence: null, rpe: 3, event_key: null, start_type: null, target_time_ms: null, gear: null },
    {
      type: "repeat",
      count: 4,
      steps: [
        { kind: "work", label: "Flying 200", notes: "Dive at the line", duration_s: null, distance_m: null, laps: 3, power: null, cadence: null, rpe: 10, event_key: "f200", start_type: "flying", target_time_ms: 11_200, gear: { chainring_teeth: 50, cog_teeth: 15 } },
      ],
    },
  ],
  estimate,
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function renderAt(path: string) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path="/workouts" element={<WorkoutsPage />} />
              <Route path="/workouts/new" element={<WorkoutEditPage />} />
              <Route path="/workouts/:workoutId" element={<WorkoutPage />} />
              <Route path="/workouts/:workoutId/edit" element={<WorkoutEditPage />} />
            </Routes>
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("workout pages", () => {
  const fetchMock = vi.fn();
  const calls = (match: (url: string, init?: RequestInit) => boolean) =>
    fetchMock.mock.calls.filter(([url, init]) => match(url as string, init as RequestInit | undefined));

  beforeEach(() => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/athletes/me")) return Promise.resolve(json({ id: "a1", user_id: "u1", club_ids: [], display_name: "Me" }));
      if (url.endsWith("/metrics/current")) return Promise.resolve(json({ on: "2026-10-30", weight_kg: null, ftp_w: { value: 300, effective_date: "2026-01-01" }, max_hr: null, resting_hr: null }));
      if (url.endsWith("/workouts/estimate")) return Promise.resolve(json(estimate));
      if (url.endsWith("/duplicate")) return Promise.resolve(json({ ...preset, id: "w2", source: "mine", can_edit: true }, 201));
      if (init?.method === "POST") return Promise.resolve(json({ ...preset, id: "w9", source: "mine", can_edit: true }, 201));
      if (/\/workouts\/w\d$/.test(url)) return Promise.resolve(json(url.endsWith("w2") ? { ...preset, id: "w2", source: "mine", can_edit: true } : preset));
      return Promise.resolve(json([summary]));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists the library and filters by a tag through the URL", async () => {
    renderAt("/workouts");
    const card = (await screen.findByRole("link", { name: "Flying 200s" })).closest("article")!;
    expect(within(card).getByText("Built-in")).toBeInTheDocument();
    expect(within(card).getByText("1 h · 55 TSS")).toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "#sprint" }));
    await waitFor(() => expect(calls((url) => url.includes("/workouts?tag=sprint"))).not.toHaveLength(0));
    await userEvent.click(screen.getByRole("radio", { name: "Mine" }));
    await waitFor(() => expect(calls((url) => url.includes("source=mine") && url.includes("tag=sprint"))).not.toHaveLength(0));
  });

  it("shows a preset read-only with its steps, and duplicating it opens the copy in the editor", async () => {
    renderAt("/workouts/w1");
    expect(await screen.findByRole("heading", { name: "Flying 200s" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.getByText("4 ×")).toBeInTheDocument();
    expect(screen.getByText("Flying 200")).toBeInTheDocument();
    expect(screen.getByText("Flying 200 · Flying start · RPE 10 · 11.200 s · 50×15")).toBeInTheDocument();
    expect(screen.getByText("Dive at the line")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Intensity profile/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Duplicate" }));
    expect(await screen.findByRole("heading", { name: "Edit workout" })).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Flying 200s");
  });

  it("builds a workout: steps and a repeat are sent as the step tree, the chart follows them", async () => {
    renderAt("/workouts/new");
    await userEvent.type(await screen.findByLabelText("Name"), "Tempo day");
    await userEvent.type(screen.getByLabelText("Tags"), "Base, tempo");

    const work = screen.getAllByRole("region", { name: "Effort" })[0];
    await userEvent.selectOptions(within(work).getByLabelText("Power"), "ftp_pct");
    await userEvent.type(within(work).getByLabelText("From"), "80");
    await userEvent.type(within(work).getAllByLabelText("To")[0], "90");
    await userEvent.click(screen.getAllByRole("button", { name: "Add a repeat" }).at(-1)!);

    await waitFor(() => expect(calls((url) => url.endsWith("/workouts/estimate")).length).toBeGreaterThan(0), { timeout: 2000 });
    const estimateBody = JSON.parse(calls((url) => url.endsWith("/workouts/estimate")).at(-1)![1]!.body as string);
    expect(estimateBody.ftp_w).toBe(300);

    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls((url, init) => url.endsWith("/workouts") && init?.method === "POST")).toHaveLength(1));
    const body = JSON.parse(calls((url, init) => url.endsWith("/workouts") && init?.method === "POST")[0][1]!.body as string);
    expect(body.name).toBe("Tempo day");
    expect(body.tags).toEqual(["base", "tempo"]);
    expect(body.steps.map((item: { kind?: string; type?: string }) => item.type ?? item.kind)).toEqual(["warmup", "work", "cooldown", "repeat"]);
    expect(body.steps[1]).toMatchObject({ duration_s: 1200, power: { unit: "ftp_pct", low: 80, high: 90 } });
    expect(body.steps[3]).toMatchObject({ count: 4, steps: [{ kind: "work", duration_s: 60 }, { kind: "recovery", duration_s: 60 }] });
  });

  it("won't save until the problems are fixed, and says where they are", async () => {
    renderAt("/workouts/new");
    const work = (await screen.findAllByRole("region", { name: "Effort" }))[0];
    await userEvent.clear(within(work).getByLabelText("Time"));
    await userEvent.type(within(work).getByLabelText("Time"), "abc");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Give it a name")).toBeInTheDocument();
    expect(within(work).getByText(/Like 45, 5:00/)).toBeInTheDocument();
    expect(calls((url, init) => url.endsWith("/workouts") && init?.method === "POST")).toHaveLength(0);
  });

  it("sends someone else's workout from its edit URL back to the read-only page", async () => {
    renderAt("/workouts/w1/edit");
    expect(await screen.findByRole("heading", { name: "Flying 200s" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
  });
});
