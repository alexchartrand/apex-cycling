import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../components/ui";
import type { AiAccess, Proposal } from "../features/aicoach/types";
import { AiCoachPage } from "./AiCoachPage";

const access: AiAccess = {
  available: true,
  enabled: true,
  consented: true,
  is_self: true,
  can_use: true,
  usage: { month_tokens: 500_000, monthly_cap: 2_000_000 },
  provider: "Mistral AI",
  model: "mistral-large-latest",
};

const proposal: Proposal = {
  id: "p1",
  kind: "adjustment",
  status: "pending",
  summary: "Move **Thursday** to Friday.",
  goal: null,
  created_at: "2026-11-12T10:00:00Z",
  expires_at: "2026-11-19T10:00:00Z",
  decided_at: null,
  conversation_id: "c1",
  items: [
    {
      op: "update",
      plan_id: "plan1",
      before: { planned_date: "2026-11-13", title: "Intervals", status: "planned", duration_s: 3600, tss: 70 },
      planned_date: "2026-11-14",
      title: "Intervals",
      description: null,
      workout_name: null,
      workout: null,
      estimate: null,
      reason: null,
      warnings: ["not_available_day"],
    },
  ],
  weeks: [{ week_start: "2026-11-09", sessions: 3, duration_s: 10_800, tss: 180 }],
  outline: [],
  errors: [],
  warnings: [],
  can_decide: true,
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function renderPage(path = "/ai-coach") {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path="/ai-coach" element={<AiCoachPage />} />
            </Routes>
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("AI coach page", () => {
  const fetchMock = vi.fn();
  let current: AiAccess = access;
  let decided: Proposal = proposal;
  let messages: unknown[] = [];

  beforeEach(() => {
    current = access;
    decided = proposal;
    messages = [];
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/athletes/me")) return Promise.resolve(json({ id: "a1", user_id: "u1", club_ids: [], display_name: "Me" }));
      if (url.endsWith("/ai-coach")) return Promise.resolve(json(current));
      if (url.endsWith("/consent")) {
        current = { ...access };
        return Promise.resolve(json(current));
      }
      if (url.endsWith("/conversations") && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        messages = [
          { id: "m1", role: "user", content: body.content, created_at: "2026-11-12T10:00:00Z", proposal: null },
          { id: "m2", role: "assistant", content: "Done — see below.", created_at: "2026-11-12T10:00:05Z", proposal: decided },
        ];
        return Promise.resolve(json({ conversation_id: "c1", messages }, 201));
      }
      if (url.endsWith("/conversations/c1")) {
        const shown = messages.map((m) => ({ ...(m as object), proposal: (m as { proposal: Proposal | null }).proposal && decided }));
        return Promise.resolve(json({ id: "c1", kind: "chat", title: "Move it", created_at: "", updated_at: null, messages: shown }));
      }
      if (url.endsWith("/proposals/p1/accept")) {
        decided = { ...proposal, status: "accepted", can_decide: false };
        return Promise.resolve(json(decided));
      }
      if (url.includes("/proposals")) return Promise.resolve(json(decided.status === "pending" ? [decided] : []));
      return Promise.resolve(json([]));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("asks for consent before anything else", async () => {
    current = { ...access, consented: false, can_use: false, usage: null };
    renderPage();
    const agree = await screen.findByRole("button", { name: "I agree, start" });
    expect(screen.getByText(/Activities from Strava are never sent/)).toBeInTheDocument();
    await userEvent.click(agree);
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/consent") && init?.method === "POST")).toBe(true));
  });

  it("says so when an admin hasn't enabled it", async () => {
    current = { ...access, enabled: false, consented: false, can_use: false, usage: null };
    renderPage();
    expect(await screen.findByText("The AI coach isn't turned on for you yet")).toBeInTheDocument();
  });

  it("chats, shows the proposal inline and accepts it", async () => {
    renderPage();
    expect(await screen.findByText("25 % of this month's AI budget used")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: "Write to your coach…" }), "Move Thursday please{Enter}");

    const card = await screen.findByRole("article", { name: "Proposed changes" });
    expect(within(card).getByText("Thursday")).toBeInTheDocument(); // bold from Markdown, as an element
    expect(within(card).getByText("Not one of your training days")).toBeInTheDocument();
    expect(within(card).getByText("Waiting for you")).toBeInTheDocument();

    await userEvent.click(within(card).getByRole("button", { name: "Accept" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/proposals/p1/accept") && init?.method === "POST")).toBe(true),
    );
  });

  it("shows a friendly message when the month's budget is spent", async () => {
    fetchMock.mockImplementationOnce(() => Promise.resolve(json({ id: "a1", user_id: "u1", club_ids: [], display_name: "Me" })));
    renderPage();
    await screen.findByRole("textbox", { name: "Write to your coach…" });
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/conversations") && init?.method === "POST") return Promise.resolve(json({ detail: "ai_coach_cap_reached" }, 429));
      if (url.endsWith("/ai-coach")) return Promise.resolve(json(access));
      return Promise.resolve(json([]));
    });
    await userEvent.type(screen.getByRole("textbox", { name: "Write to your coach…" }), "Hello{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("This month's AI budget is used up");
  });
});
