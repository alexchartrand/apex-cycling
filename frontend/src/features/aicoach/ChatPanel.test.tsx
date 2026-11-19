import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode, useState } from "react";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../../components/ui";
import * as api from "./api";
import type { Conversation } from "./types";
import { ChatPanel } from "./ChatPanel";

vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  listConversations: vi.fn(async () => []),
  fetchConversation: vi.fn(),
  // A reply that never ends, like an intake still being written.
  startConversation: vi.fn(() => new Promise(() => {})),
  sendMessage: vi.fn(() => new Promise(() => {})),
}));

afterEach(() => vi.clearAllMocks());

/** The page's wiring of `build`, without its access checks. */
function Page({ remountKey }: { remountKey: number }) {
  const [params, setParams] = useSearchParams();
  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [name, value] of Object.entries(changes)) {
      if (value === null) next.delete(name);
      else next.set(name, value);
    }
    setParams(next, { replace: true });
  };
  return (
    <ChatPanel
      key={remountKey}
      athleteId="a1"
      conversationId={params.get("c")}
      build={params.get("build")}
      onBuildStarted={() => update({ build: null })}
      onOpen={(id) => update({ c: id, build: null })}
    />
  );
}

function Harness() {
  const [remountKey, setRemountKey] = useState(0);
  return (
    <>
      <button type="button" onClick={() => setRemountKey((k) => k + 1)}>
        remount
      </button>
      <Routes>
        <Route path="/ai-coach" element={<Page remountKey={remountKey} />} />
      </Routes>
    </>
  );
}

function renderAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <TooltipProvider>
          <ToastProvider>
            <MemoryRouter initialEntries={[url]}>
              <Harness />
            </MemoryRouter>
          </ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
}

const reply = {
  id: "m1",
  role: "assistant",
  content: "A few things I still need",
  created_at: "2026-11-19T10:00:00Z",
  proposal: null,
} as unknown as Conversation["messages"][number];

describe("ChatPanel ?build=", () => {
  it("opens the conversation and frees the composer when the reply ends", async () => {
    vi.mocked(api.startConversation).mockResolvedValueOnce({ conversation_id: "c1", messages: [reply] });
    vi.mocked(api.fetchConversation).mockResolvedValue({
      id: "c1",
      kind: "intake",
      title: null,
      created_at: "2026-11-19T10:00:00Z",
      updated_at: null,
      messages: [reply],
    } as unknown as Conversation);
    renderAt("/ai-coach?tab=chat&build=new");
    await waitFor(() => expect(api.fetchConversation).toHaveBeenCalledWith("a1", "c1"));
    await screen.findByText("A few things I still need");
    await waitFor(() => expect(screen.getByRole("textbox")).not.toBeDisabled());
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("starts one intake for the plan, even when the panel mounts again mid-reply", async () => {
    const view = renderAt("/ai-coach?tab=chat&build=plan-1");
    await vi.waitFor(() => expect(api.startConversation).toHaveBeenCalledTimes(1));
    view.getByText("remount").click();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(api.startConversation).toHaveBeenCalledTimes(1);
    expect(vi.mocked(api.startConversation).mock.calls[0][1]).toEqual({ kind: "intake", training_plan_id: "plan-1" });
  });

  it("starts a new-plan intake once", async () => {
    renderAt("/ai-coach?tab=chat&build=new");
    await vi.waitFor(() => expect(api.startConversation).toHaveBeenCalledTimes(1));
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(api.startConversation).toHaveBeenCalledTimes(1);
    expect(vi.mocked(api.startConversation).mock.calls[0][1]).toEqual({ kind: "intake" });
  });
});

describe("ChatPanel reply in flight", () => {
  it("stays in its own conversation when another one is opened", async () => {
    const summary = (id: string, title: string) => ({ id, kind: "chat", title, created_at: "2026-11-19T10:00:00Z", updated_at: null });
    vi.mocked(api.listConversations).mockResolvedValue([summary("c1", "Plan talk"), summary("c2", "Other talk")] as never);
    vi.mocked(api.fetchConversation).mockImplementation(
      async (_athlete, id) => ({ ...summary(id, id), messages: id === "c1" ? [reply] : [] }) as unknown as Conversation,
    );
    renderAt("/ai-coach?tab=chat&c=c1");
    await screen.findByText("A few things I still need");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "6h, yes, yes" } });
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    await screen.findByRole("status");
    expect(screen.getByRole("textbox")).toHaveValue("");

    fireEvent.click(screen.getByText("Other talk"));
    await waitFor(() => expect(api.fetchConversation).toHaveBeenCalledWith("a1", "c2"));
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
    expect(screen.queryByText("6h, yes, yes")).toBeNull();
    expect(screen.getByText("Replying…")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Plan talk"));
    await screen.findByRole("status");
    expect(screen.getByText("6h, yes, yes")).toBeInTheDocument();
  });
});
