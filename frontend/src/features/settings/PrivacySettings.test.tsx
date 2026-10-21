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
const athlete = (over: Partial<Athlete> = {}): Athlete => ({
  id: "a1",
  user_id: "u1",
  club_id: "c1",
  display_name: "Me",
  birthdate: null,
  sex: null,
  height_cm: null,
  category: null,
  leaderboard_opt_in: false,
  ...over,
});

describe("PrivacySettings", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(athlete({ leaderboard_opt_in: true })), { status: 200 }));
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

  it("opts in with a PATCH of just that setting", async () => {
    renderSettings(athlete());
    const checkbox = screen.getByRole("checkbox", { name: /best times on my club's leaderboard/ });
    expect(checkbox).not.toBeChecked();
    await userEvent.setup().click(checkbox);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/athletes/a1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ leaderboard_opt_in: true });
  });

  it("is off the table without a club", () => {
    renderSettings(athlete({ club_id: null }));
    expect(screen.getByRole("checkbox")).toBeDisabled();
    expect(screen.getByText(/aren't on a club's roster/)).toBeInTheDocument();
  });

  it("isn't a coach's to change on an athlete's behalf", () => {
    renderSettings(athlete({ user_id: "someone-else", leaderboard_opt_in: true }));
    expect(screen.getByRole("checkbox")).toBeDisabled();
    expect(screen.getByText("Only the athlete decides this setting.")).toBeInTheDocument();
  });

  it("a club admin can decide for a managed athlete", () => {
    renderSettings(athlete({ user_id: null }));
    expect(screen.getByRole("checkbox")).toBeEnabled();
  });
});
