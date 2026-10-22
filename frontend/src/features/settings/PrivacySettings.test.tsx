import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/ui";
import type { Athlete } from "../athletes/types";
import type { User } from "../auth/types";
import { PrivacySettings } from "./PrivacySettings";

const user = { id: "u1", email: "me@example.com" } as User;
const clubs = [
  { id: "c1", name: "CNCB", slug: "cncb", timezone: "UTC", role: "athlete" },
  { id: "c2", name: "Velo Nord", slug: "velo-nord", timezone: "UTC", role: "athlete" },
];
const athlete = (over: Partial<Athlete> = {}): Athlete => ({
  id: "a1",
  user_id: "u1",
  club_ids: ["c1"],
  display_name: "Me",
  birthdate: null,
  sex: null,
  height_cm: null,
  category: null,
  leaderboard_club_ids: [],
  ...over,
});

describe("PrivacySettings", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockImplementation(async (url: string) =>
      url === "/api/clubs"
        ? new Response(JSON.stringify(clubs), { status: 200 })
        : new Response(JSON.stringify(athlete({ leaderboard_club_ids: ["c1"] })), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  function renderSettings(a: Athlete) {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
        <ToastProvider>
          <MemoryRouter>
            <PrivacySettings athlete={a} user={user} />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  const clubCalls = () => fetchMock.mock.calls.filter(([url]) => url !== "/api/clubs");

  it("opts in to one club with a PUT of just that club", async () => {
    renderSettings(athlete());
    const checkbox = await screen.findByRole("checkbox", { name: "Show my best times on the CNCB leaderboard" });
    expect(checkbox).not.toBeChecked();
    await userEvent.setup().click(checkbox);
    await waitFor(() => expect(clubCalls()).toHaveLength(1));
    const [url, init] = clubCalls()[0];
    expect(url).toBe("/api/athletes/a1/clubs/c1/leaderboard");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ opt_in: true });
  });

  it("has a choice per club the athlete rides for", async () => {
    renderSettings(athlete({ club_ids: ["c1", "c2"], leaderboard_club_ids: ["c2"] }));
    expect(await screen.findByRole("checkbox", { name: /CNCB leaderboard/ })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Velo Nord leaderboard/ })).toBeChecked();
  });

  it("is off the table without a club", async () => {
    renderSettings(athlete({ club_ids: [] }));
    expect(await screen.findByText(/aren't on a club's roster/)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("isn't a coach's to change on an athlete's behalf", async () => {
    renderSettings(athlete({ user_id: "someone-else", leaderboard_club_ids: ["c1"] }));
    expect(await screen.findByRole("checkbox")).toBeDisabled();
    expect(screen.getByText("Only the athlete decides this setting.")).toBeInTheDocument();
  });

  it("a club admin can decide for a managed athlete", async () => {
    renderSettings(athlete({ user_id: null }));
    expect(await screen.findByRole("checkbox")).toBeEnabled();
  });
});
