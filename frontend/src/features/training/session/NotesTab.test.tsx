import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../../components/ui";
import type { SessionDetail } from "../types";
import { NotesTab } from "./NotesTab";
import { changesFrom } from "./notesDraft";

const session: SessionDetail = {
  external_event_id: "evt1",
  event_name: "Openers",
  original_name: "Session quotidienne 2026-07-07",
  title_override: "Openers",
  event_date: "2026-07-07",
  notes: "Felt flat",
  rpe: 7,
  tags: ["track"],
  is_race: false,
  tracks: [],
};

const draft = (over: Partial<Parameters<typeof changesFrom>[1]> = {}) => ({
  title: "Openers",
  rpe: "7",
  notes: "Felt flat",
  tags: ["track"],
  isRace: false,
  ...over,
});

describe("changesFrom", () => {
  it("is empty when nothing changed (surrounding whitespace doesn't count)", () => {
    expect(changesFrom(session, draft())).toEqual({});
    expect(changesFrom(session, draft({ title: "  Openers ", notes: "Felt flat\n" }))).toEqual({});
  });

  it("reports only what differs, and blank / unrated clear a field", () => {
    expect(changesFrom(session, draft({ rpe: "", title: "", notes: "  " }))).toEqual({
      title_override: null,
      rpe: null,
      notes: null,
    });
    expect(changesFrom(session, draft({ rpe: "9", tags: ["track", "kilo"] }))).toEqual({ rpe: 9, tags: ["track", "kilo"] });
    expect(changesFrom(session, draft({ isRace: true }))).toEqual({ is_race: true });
  });
});

describe("NotesTab", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ...session, event_name: "Kilo day" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  function renderTab(client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })) {
    render(
      <QueryClientProvider client={client}>
        <ToastProvider>
          <NotesTab athleteId="a1" session={session} />
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("shows the saved values and keeps Save disabled until something changes", () => {
    renderTab();
    expect(screen.getByLabelText("Session title")).toHaveValue("Openers");
    expect(screen.getByLabelText("Perceived effort (RPE)")).toHaveValue("7");
    expect(screen.getByLabelText("Notes")).toHaveValue("Felt flat");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("PATCHes just the changed fields", async () => {
    renderTab();
    const user = userEvent.setup();
    const title = screen.getByLabelText("Session title");
    await user.clear(title);
    await user.type(title, "Kilo day");
    await user.selectOptions(screen.getByLabelText("Perceived effort (RPE)"), "9");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/athletes/a1/sessions/evt1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ title_override: "Kilo day", rpe: 9 });
  });

  it("marking the session as a race refreshes the race calendar and the season tiles", async () => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    renderTab(client);
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("This session was a race"));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ is_race: true }));
    await waitFor(() => {
      const keys = invalidate.mock.calls.map(([filters]) => (filters as { queryKey: unknown[] }).queryKey[0]);
      expect(keys).toEqual(expect.arrayContaining(["competitions", "season-summary", "sessions", "session-detail"]));
    });
  });
});
