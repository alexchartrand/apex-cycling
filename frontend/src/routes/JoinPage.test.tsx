import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/ui";
import { JoinPage } from "./JoinPage";

const TOKEN = "q3Zr8a-1X_Lm0pTYb7nHc2VdE5uKfGiJ9sWoA4xRNkU";

describe("JoinPage", () => {
  const fetchMock = vi.fn();
  let preview: { status: number; body: unknown };

  beforeEach(() => {
    preview = { status: 200, body: { club_name: "CNCB", role: "athlete", already_member: false } };
    fetchMock.mockImplementation(async (url: string) => {
      if (url === "/api/invites/preview") return new Response(JSON.stringify(preview.body), { status: preview.status });
      if (url === "/api/invites/accept") {
        return new Response(JSON.stringify({ id: "club-1", name: "CNCB", slug: "cncb", timezone: "UTC", role: "athlete" }), { status: 200 });
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  function renderAt(entry: string) {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
        <ToastProvider>
          <MemoryRouter initialEntries={[entry]}>
            <Routes>
              <Route path="/join" element={<JoinPage />} />
              <Route path="/club" element={<p>clubs list</p>} />
              <Route path="/club/:clubId" element={<p>club page</p>} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  const bodyOf = (url: string) => JSON.parse(fetchMock.mock.calls.find(([u]) => u === url)![1].body);

  it("says what you're joining and what that means, and joins on request", async () => {
    renderAt(`/join#token=${TOKEN}`);
    const user = userEvent.setup();
    expect(await screen.findByText("You're invited to CNCB")).toBeInTheDocument();
    expect(screen.getByText("You'll join as: athlete.")).toBeInTheDocument();
    // Joining as an athlete hands the club's admins access: that has to be said up front.
    expect(screen.getByText(/the club's admins will be able to see and manage your training data/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/invites/accept")).toBe(false);

    await user.click(screen.getByRole("button", { name: "Join club" }));
    expect(await screen.findByText("club page")).toBeInTheDocument();
    expect(bodyOf("/api/invites/accept")).toEqual({ token: TOKEN });
    // The token goes in the body, never the URL.
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes(TOKEN))).toBe(true);
  });

  it("describes a coach invitation differently", async () => {
    preview.body = { club_name: "CNCB", role: "coach", already_member: false };
    renderAt(`/join#token=${TOKEN}`);
    expect(await screen.findByText(/you can ask to coach athletes/)).toBeInTheDocument();
  });

  it("offers to open the club when already a member", async () => {
    preview.body = { club_name: "CNCB", role: "athlete", already_member: true };
    renderAt(`/join#token=${TOKEN}`);
    expect(await screen.findByText("You're already a member of CNCB.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open club" })).toBeInTheDocument();
  });

  it("explains a link that is dead", async () => {
    preview = { status: 400, body: { detail: "This invite link is invalid, has expired or has been used up" } };
    renderAt(`/join#token=${TOKEN}`);
    expect(await screen.findByText("This invitation can't be used")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Join club" })).not.toBeInTheDocument();
  });

  it("asks for a link when there is none, and never calls the server", async () => {
    renderAt("/join");
    expect(await screen.findByText("No invitation link")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("ignores a token that isn't shaped like one", async () => {
    renderAt("/join#token=<script>");
    expect(await screen.findByText("No invitation link")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled());
  });
});
