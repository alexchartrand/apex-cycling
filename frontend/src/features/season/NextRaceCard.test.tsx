import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRaceCard } from "./NextRaceCard";
import type { Competition } from "./types";

const race = (over: Partial<Competition>): Competition => ({
  id: "c1",
  name: "Nationals",
  competition_date: "2099-07-20",
  priority: "A",
  location: "Bromont",
  notes: null,
  goal: null,
  days_until: 12,
  taper_starts_on: "2099-07-10",
  days_to_taper: 3,
  phase: "build",
  race_session_id: null,
  ...over,
});

function renderCard() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <NextRaceCard athleteId="a1" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("NextRaceCard", () => {
  const fetchMock = vi.fn();
  let list: Competition[];

  beforeEach(() => {
    list = [];
    fetchMock.mockImplementation(() => Promise.resolve(new Response(JSON.stringify(list), { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("shows the next race with its countdown", async () => {
    list = [race({ id: "past", name: "Old race", days_until: -5, phase: "past" }), race({})];
    renderCard();
    expect(await screen.findByText("Nationals")).toBeInTheDocument();
    expect(screen.getByText("In 12 days")).toBeInTheDocument();
    expect(screen.queryByText("Old race")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "All races" })).toHaveAttribute("href", "/season");
  });

  it("says when the taper is on", async () => {
    list = [race({ days_until: 4, phase: "taper" })];
    renderCard();
    expect(await screen.findByText(/You are in the taper/)).toBeInTheDocument();
  });

  it("renders nothing without a race ahead", async () => {
    list = [race({ days_until: -2, phase: "past" })];
    const { container } = (() => {
      renderCard();
      return { container: document.body };
    })();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(container.querySelector(".ui-card")).toBeNull();
  });
});
