import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../../components/ui";
import { setViewingAthleteId } from "../athletes/viewing";
import { NotificationBell } from "./NotificationBell";
import type { AppNotification, NotificationPreferences } from "./types";
import { NotificationSettings } from "./NotificationSettings";

const viewing = () => sessionStorage.getItem("apex-viewing-athlete");

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

const record: AppNotification = {
  id: "n1",
  kind: "new_pr",
  payload: { external_event_id: "evt-1", session_name: "Kilo day", count: 1, items: [{ event_key: "500m", time_ms: 47_535 }] },
  created_at: new Date().toISOString(),
  read_at: null,
};
const comment: AppNotification = {
  id: "n2",
  kind: "comment",
  payload: { author_name: "Rider", athlete_id: "ath-9", external_event_id: "evt-2", session_name: "Tuesday", excerpt: "Legs felt heavy" },
  created_at: new Date().toISOString(),
  read_at: new Date().toISOString(),
};

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function renderWith(ui: React.ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter>
            <Routes>
              <Route path="*" element={<>{ui}<Where /></>} />
            </Routes>
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("NotificationBell", () => {
  const fetchMock = vi.fn();
  let unread = 1;

  beforeEach(() => {
    unread = 1;
    setViewingAthleteId(null);
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/notifications/unread-count")) return Promise.resolve(json({ count: unread }));
      if (url.endsWith("/notifications/read")) return Promise.resolve(new Response(null, { status: 204 }));
      if (url.endsWith("/athletes/me")) return Promise.resolve(json({ id: "me-1", display_name: "Coach", user_id: "u1" }));
      if (url.endsWith("/notifications") && !init?.method) return Promise.resolve(json([record, comment]));
      return Promise.resolve(json({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("shows the unread count on the bell and the notifications in a panel", async () => {
    renderWith(<NotificationBell variant="row" />);
    const bell = await screen.findByRole("button", { name: "Notifications, 1 unread" });
    await userEvent.click(bell);

    expect(await screen.findByText("New record · 500 m")).toBeInTheDocument();
    expect(screen.getByText("Kilo day · 47.535 s")).toBeInTheDocument();
    expect(screen.getByText("Rider commented")).toBeInTheDocument();
    expect(screen.getByText("Tuesday: Legs felt heavy")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notification settings" })).toHaveAttribute("href", "/settings/notifications");
  });

  it("opens a record, marks it read and closes the panel", async () => {
    renderWith(<NotificationBell variant="row" />);
    await userEvent.click(await screen.findByRole("button", { name: /Notifications, 1 unread/ }));
    await userEvent.click(await screen.findByText("New record · 500 m"));

    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/sessions/evt-1"));
    const read = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/notifications/read"));
    expect(JSON.parse(read![1].body)).toEqual({ ids: ["n1"] });
    expect(screen.queryByText("Rider commented")).not.toBeInTheDocument();
    expect(viewing()).toBeNull();
  });

  it("opens a comment as the athlete it is about", async () => {
    renderWith(<NotificationBell variant="icon" />);
    await userEvent.click(await screen.findByRole("button", { name: /Notifications/ }));
    await userEvent.click(await screen.findByText("Rider commented"));

    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/sessions/evt-2?tab=comments"));
    expect(viewing()).toBe("ath-9");
    // Already read: nothing is sent.
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/notifications/read"))).toBe(false);
  });

  it("marks everything read", async () => {
    renderWith(<NotificationBell variant="row" />);
    await userEvent.click(await screen.findByRole("button", { name: /Notifications, 1 unread/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Mark all read" }));
    await waitFor(() => {
      const read = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/notifications/read"));
      expect(JSON.parse(read![1].body)).toEqual({});
    });
  });

  it("has no count when everything is read", async () => {
    unread = 0;
    renderWith(<NotificationBell variant="row" />);
    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
  });
});

describe("NotificationSettings", () => {
  const fetchMock = vi.fn();
  const channels = { in_app: true, push: true, email: true };
  const prefs: NotificationPreferences = {
    kinds: {
      new_pr: { ...channels, email: false },
      comment: channels,
      coach_request: channels,
      plan_added: channels,
      sync_failed: channels,
    },
    email_available: false,
    push_available: true,
  };

  beforeEach(() => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/notifications/preferences") && init?.method === "PUT") {
        const sent = JSON.parse(String(init.body)).kinds as Record<string, typeof channels>;
        return Promise.resolve(json({ ...prefs, kinds: { ...prefs.kinds, ...sent } }));
      }
      if (url.endsWith("/notifications/preferences")) return Promise.resolve(json(prefs));
      if (url.endsWith("/notifications/push")) return Promise.resolve(json({ enabled: false, public_key: null }));
      return Promise.resolve(json({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("shows a checkbox per event and channel, disabling the channels the server can't send", async () => {
    renderWith(<NotificationSettings />);
    const commentPush = await screen.findByRole("checkbox", { name: "Comments — Push" });
    expect(commentPush).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "New records — Email" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Comments — Email" })).toBeDisabled(); // no SMTP
    expect(screen.getByText("Push isn't set up on this server yet.")).toBeInTheDocument();
  });

  it("saves one event's row when a channel is toggled", async () => {
    renderWith(<NotificationSettings />);
    await userEvent.click(await screen.findByRole("checkbox", { name: "Comments — Push" }));
    await waitFor(() => {
      const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
      expect(JSON.parse(put![1].body)).toEqual({ kinds: { comment: { in_app: true, push: false, email: true } } });
    });
    await waitFor(() => expect(screen.getByRole("checkbox", { name: "Comments — Push" })).not.toBeChecked());
  });
});
