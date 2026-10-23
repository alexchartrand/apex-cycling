import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/ui";
import { PowerProfileCard } from "./PowerProfileCard";
import type { PowerProfile } from "./types";

const profile: PowerProfile = {
  days: 90,
  critical_power: { cp_w: 300, w_prime_j: 20000, r_squared: 0.995, points: 5 },
  ftp_current_w: 270,
  ftp_suggestion: { ftp_w: 285.4, source_duration_s: 1200, source_activity_id: "act1", source_power_w: 300.4 },
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function renderCard() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } })}>
      <ToastProvider>
        <PowerProfileCard athleteId="a1" />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("PowerProfileCard", () => {
  const fetchMock = vi.fn();
  let current: PowerProfile;

  beforeEach(() => {
    localStorage.clear();
    current = profile;
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes("/power-profile")) return Promise.resolve(json(current));
      if (url.includes("/metrics/current")) return Promise.resolve(json({ weight_kg: { value: 75, effective_date: "2026-01-01" } }));
      if (url.endsWith("/metrics") && init?.method === "POST") return Promise.resolve(json({ id: "m1" }, 201));
      return Promise.resolve(json({}));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("shows critical power with its per-kilo figure and W′", async () => {
    renderCard();
    expect(await screen.findByText("300")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("4.00 W/kg")).toBeInTheDocument();
  });

  it("offers the suggested FTP and saves it as today's value", async () => {
    renderCard();
    await userEvent.click(await screen.findByRole("button", { name: /285/ }));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/metrics") && init?.method === "POST");
      expect(post).toBeDefined();
      expect(JSON.parse(post![1].body)).toMatchObject({ ftp_w: 285 });
    });
  });

  it("stops asking once dismissed", async () => {
    renderCard();
    await userEvent.click(await screen.findByRole("button", { name: /not now|pas maintenant/i }));
    await waitFor(() => expect(screen.queryByRole("button", { name: /285/ })).not.toBeInTheDocument());
    expect(localStorage.getItem("ftp-suggestion-dismissed:a1")).toBe("285");
  });

  it("says there is not enough data when no line can be fitted", async () => {
    current = { ...profile, critical_power: null, ftp_suggestion: null };
    renderCard();
    expect(await screen.findByText(/Not enough data|Pas encore assez/)).toBeInTheDocument();
  });
});
