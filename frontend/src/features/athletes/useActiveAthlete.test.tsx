import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Athlete } from "./types";
import { useActiveAthlete, useViewingOther } from "./useActiveAthlete";
import { useMyAthlete } from "./useAthlete";
import { setViewingAthleteId, useViewingAthleteId } from "./viewing";
import { useViewAthlete } from "./useViewAthlete";

const athlete = (id: string, name: string): Athlete => ({
  id,
  user_id: null,
  club_id: null,
  display_name: name,
  birthdate: null,
  sex: null,
  height_cm: null,
  category: null,
  leaderboard_opt_in: false,
});

describe("active athlete", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    setViewingAthleteId(null);
    fetchMock.mockImplementation(async (url: string) => {
      if (url === "/api/athletes/me") return new Response(JSON.stringify(athlete("me", "Me")), { status: 200 });
      if (url === "/api/athletes/rider") return new Response(JSON.stringify(athlete("rider", "Rider")), { status: 200 });
      return new Response(JSON.stringify({ detail: "Not authorized for this athlete" }), { status: 403 });
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    setViewingAthleteId(null);
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );

  it("is the signed-in user's own athlete by default", async () => {
    const { result } = renderHook(() => ({ active: useActiveAthlete(), other: useViewingOther() }), { wrapper });
    await waitFor(() => expect(result.current.active.data?.display_name).toBe("Me"));
    expect(result.current.other.viewing).toBeUndefined();
    expect(fetchMock.mock.calls.map(([url]) => url)).not.toContain("/api/athletes/rider");
  });

  it("shows another athlete once chosen, and says so", async () => {
    setViewingAthleteId("rider");
    const { result } = renderHook(() => ({ active: useActiveAthlete(), other: useViewingOther() }), { wrapper });
    await waitFor(() => expect(result.current.active.data?.display_name).toBe("Rider"));
    expect(result.current.other.viewing?.display_name).toBe("Rider");
  });

  it("goes back to the user's own data when access to the chosen athlete is lost", async () => {
    setViewingAthleteId("revoked");
    const { result } = renderHook(() => ({ active: useActiveAthlete(), viewingId: useViewingAthleteId() }), { wrapper });
    await waitFor(() => expect(result.current.viewingId).toBeNull());
    await waitFor(() => expect(result.current.active.data?.display_name).toBe("Me"));
  });

  it("switching to my own athlete clears the choice instead of storing it", async () => {
    setViewingAthleteId("rider");
    const { result } = renderHook(() => ({ view: useViewAthlete(), viewingId: useViewingAthleteId(), me: useMyAthlete() }), { wrapper });
    await waitFor(() => expect(result.current.me.data?.id).toBe("me"));

    act(() => result.current.view("me"));
    expect(result.current.viewingId).toBeNull();
    act(() => result.current.view("rider"));
    expect(result.current.viewingId).toBe("rider");
  });
});
