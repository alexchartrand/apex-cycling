import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/ui";
import { CommentsTab } from "./CommentsTab";
import type { SessionComment } from "./types";

const comment = (over: Partial<SessionComment>): SessionComment => ({
  id: "c1",
  author_user_id: "u1",
  author_name: "Rider",
  by_athlete: true,
  body: "Legs felt heavy",
  created_at: "2026-10-19T12:00:00Z",
  edited_at: null,
  can_edit: true,
  can_delete: true,
  ...over,
});

const mine = comment({});
const coachs = comment({
  id: "c2",
  author_user_id: "u2",
  author_name: "Coach",
  by_athlete: false,
  body: "Keep the next one easy",
  can_edit: false,
  can_delete: true,
});

describe("CommentsTab", () => {
  const fetchMock = vi.fn();
  let thread: SessionComment[];

  beforeEach(() => {
    thread = [mine, coachs];
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (method === "GET") return new Response(JSON.stringify(thread), { status: 200 });
      if (method === "POST" && url.endsWith("/read")) return new Response(null, { status: 204 });
      if (method === "POST") return new Response(JSON.stringify(comment({ id: "c3", body: JSON.parse(String(init?.body)).body })), { status: 201 });
      return new Response(null, { status: 204 });
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  function renderTab() {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
        <ToastProvider>
          <CommentsTab athleteId="a1" eventId="evt 1" />
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  const calls = (method: string) => fetchMock.mock.calls.filter(([, init]) => (init?.method ?? "GET") === method);

  it("shows the thread, labels who wrote what and offers only the actions allowed", async () => {
    renderTab();
    expect(await screen.findByText("Legs felt heavy")).toBeInTheDocument();
    expect(screen.getByText("Keep the next one easy")).toBeInTheDocument();
    expect(screen.getByText("Athlete")).toBeInTheDocument();
    expect(screen.getByText("Coach", { selector: ".badge" })).toBeInTheDocument();

    const items = screen.getAllByRole("listitem");
    // Mine: edit and delete. The coach's: delete only (the athlete may remove it).
    expect(within(items[0]).getByRole("button", { name: "Edit comment" })).toBeInTheDocument();
    expect(within(items[1]).queryByRole("button", { name: "Edit comment" })).not.toBeInTheDocument();
    expect(within(items[1]).getByRole("button", { name: "Delete comment" })).toBeInTheDocument();
    expect(calls("GET")[0][0]).toBe("/api/athletes/a1/sessions/evt%201/comments");
  });

  it("tells the server the thread was read once there are comments from others", async () => {
    renderTab();
    await screen.findByText("Keep the next one easy");
    await waitFor(() => expect(calls("POST").map(([url]) => url)).toContain("/api/athletes/a1/sessions/evt%201/comments/read"));
  });

  it("does not mark a thread of only my own comments as read", async () => {
    thread = [mine];
    renderTab();
    await screen.findByText("Legs felt heavy");
    expect(calls("POST")).toHaveLength(0);
  });

  it("posts a trimmed comment, and Send stays disabled while the box is blank", async () => {
    renderTab();
    const user = userEvent.setup();
    await screen.findByText("Legs felt heavy");
    const send = screen.getByRole("button", { name: "Send" });
    expect(send).toBeDisabled();

    await user.type(screen.getByLabelText("Add a comment"), "  See you Thursday  ");
    expect(send).toBeEnabled();
    await user.click(send);

    await waitFor(() => expect(calls("POST").some(([url]) => url.endsWith("/comments"))).toBe(true));
    const [, init] = calls("POST").find(([url]) => url.endsWith("/comments"))!;
    expect(JSON.parse(init.body)).toEqual({ body: "See you Thursday" });
    await waitFor(() => expect(screen.getByLabelText("Add a comment")).toHaveValue(""));
  });

  it("sends with Ctrl+Enter", async () => {
    renderTab();
    const user = userEvent.setup();
    await screen.findByText("Legs felt heavy");
    await user.type(screen.getByLabelText("Add a comment"), "Quick note{Control>}{Enter}{/Control}");
    await waitFor(() => expect(calls("POST").some(([url]) => url.endsWith("/comments"))).toBe(true));
  });

  it("edits my comment in place", async () => {
    renderTab();
    const user = userEvent.setup();
    await screen.findByText("Legs felt heavy");
    await user.click(within(screen.getAllByRole("listitem")[0]).getByRole("button", { name: "Edit comment" }));
    const box = screen.getByRole("textbox", { name: "Edit comment" });
    expect(box).toHaveValue("Legs felt heavy");
    await user.clear(box);
    await user.type(box, "Legs felt fine");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(calls("PATCH")).toHaveLength(1));
    expect(calls("PATCH")[0][0]).toBe("/api/athletes/a1/sessions/evt%201/comments/c1");
    expect(JSON.parse(calls("PATCH")[0][1].body)).toEqual({ body: "Legs felt fine" });
  });

  it("asks before deleting", async () => {
    renderTab();
    const user = userEvent.setup();
    await screen.findByText("Keep the next one easy");
    await user.click(within(screen.getAllByRole("listitem")[1]).getByRole("button", { name: "Delete comment" }));
    expect(calls("DELETE")).toHaveLength(0);
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() => expect(calls("DELETE")).toHaveLength(1));
    expect(calls("DELETE")[0][0]).toBe("/api/athletes/a1/sessions/evt%201/comments/c2");
  });

  it("invites the first comment when the thread is empty", async () => {
    thread = [];
    renderTab();
    expect(await screen.findByText("No comments yet")).toBeInTheDocument();
  });
});
