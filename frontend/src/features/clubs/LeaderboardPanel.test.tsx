import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../../components/ui";
import { LeaderboardPanel } from "./LeaderboardPanel";
import type { Club, Leaderboard } from "./types";

const club: Club = { id: "c1", name: "CNCB", slug: "cncb", timezone: "UTC", role: "athlete" };

const board: Leaderboard = {
  event_key: "1km",
  start_type: "standing",
  track_id: "t1",
  track_name: "Bromont",
  participants: 3,
  categories: ["U19", "M30"],
  entries: [
    { rank: 1, display_name: "Ann", time_ms: 68_000, achieved_on: "2026-06-01", sex: "female", category: "U19", source: "sqorz", is_me: false },
    { rank: 1, display_name: "Bob", time_ms: 68_000, achieved_on: "2026-06-02", sex: "male", category: "U19", source: "manual", is_me: true },
    { rank: 3, display_name: "Cleo", time_ms: 70_250, achieved_on: "2026-06-03", sex: "female", category: null, source: "sqorz", is_me: false },
  ],
};

const me = { id: "a1", user_id: "u1", club_id: "c1", display_name: "Bob", birthdate: null, sex: null, height_cm: null, category: null, leaderboard_opt_in: false };

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });

function renderPanel() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter>
            <LeaderboardPanel club={club} />
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("LeaderboardPanel", () => {
  const fetchMock = vi.fn();
  let current: Leaderboard;
  let tracks: { id: string; name: string }[];

  beforeEach(() => {
    current = board;
    tracks = [{ id: "t1", name: "Bromont" }, { id: "t2", name: "Indoor" }];
    fetchMock.mockImplementation((url: string) => {
      if (url.includes("/leaderboard")) return Promise.resolve(json(current));
      if (url.endsWith("/tracks")) return Promise.resolve(json(tracks));
      return Promise.resolve(json(me));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  const leaderboardUrls = () => fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/leaderboard"));

  it("ranks the athletes who opted in, equal times sharing a rank, and marks the viewer", async () => {
    renderPanel();
    expect(await screen.findByText("Ann")).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("1:08.000")).toBeInTheDocument();
    expect(within(rows[1]).getByText("You")).toBeInTheDocument();
    expect(within(rows[2]).getByText("3")).toBeInTheDocument();
    expect(within(rows[2]).getByText("1:10.250")).toBeInTheDocument();
    expect(screen.getByText("3 athletes have opted in.")).toBeInTheDocument();
  });

  it("asks for the first track's kilo to start with, and re-asks when a filter changes", async () => {
    renderPanel();
    await screen.findByText("Ann");
    expect(leaderboardUrls()[0]).toBe("/api/clubs/c1/leaderboard?event_key=1km&start_type=standing&track_id=t1");

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Racing category"), "Women");
    await waitFor(() => expect(leaderboardUrls().some((url) => url.includes("sex=female"))).toBe(true));
    await user.selectOptions(screen.getByLabelText("Age category"), "U19");
    await waitFor(() => expect(leaderboardUrls().some((url) => url.includes("category=U19"))).toBe(true));
    await user.selectOptions(screen.getByLabelText("Track"), "Indoor");
    await waitFor(() => expect(leaderboardUrls().some((url) => url.includes("track_id=t2"))).toBe(true));
  });

  it("a flying-only event fixes the start", async () => {
    renderPanel();
    await screen.findByText("Ann");
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Event"), "Flying 200");
    await waitFor(() => expect(leaderboardUrls().some((url) => url.includes("event_key=f200&start_type=flying"))).toBe(true));
    expect(screen.getByLabelText("Start")).toBeDisabled();
  });

  it("links an athlete who is on the roster but not on the leaderboard to the privacy setting", async () => {
    renderPanel();
    expect(await screen.findByRole("link", { name: "Appear on the leaderboard" })).toHaveAttribute("href", "/settings/privacy");
  });

  it("says when nobody has opted in", async () => {
    current = { ...board, participants: 0, categories: [], entries: [] };
    renderPanel();
    expect(await screen.findByText("Nobody has opted in yet.")).toBeInTheDocument();
  });

  it("explains an empty club with no tracks", async () => {
    tracks = [];
    renderPanel();
    expect(await screen.findByText("No tracks yet")).toBeInTheDocument();
    expect(leaderboardUrls()).toHaveLength(0);
  });
});
