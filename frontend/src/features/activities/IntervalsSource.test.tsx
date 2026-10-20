import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/ui";
import { IntervalsSource } from "./IntervalsSource";

const disconnected = { connected: false, active: false, intervals_athlete_id: null, intervals_athlete_name: null, last_synced_at: null, runs: [] };
const connected = {
  connected: true,
  active: true,
  intervals_athlete_id: "i42",
  intervals_athlete_name: "Alex",
  last_synced_at: null,
  runs: [{ status: "success", requested_at: "2026-06-01T07:00:00Z", completed_at: "2026-06-01T07:00:05Z", error_message: null, imported_count: 3 }],
};

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("IntervalsSource", () => {
  const fetchMock = vi.fn();

  beforeEach(() => vi.stubGlobal("fetch", fetchMock));
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  function renderCard() {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ToastProvider>
          <IntervalsSource athleteId="ath-1" />
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("connects with the pasted key, never shows it back, and lists the sync history", async () => {
    fetchMock.mockResolvedValueOnce(json(disconnected)).mockResolvedValueOnce(json(connected));
    renderCard();

    const input = await screen.findByLabelText("API key");
    const connect = screen.getByRole("button", { name: "Connect" });
    expect(connect).toBeDisabled(); // too short to be a key
    await userEvent.type(input, "  my-secret-key-123  ");
    await userEvent.click(connect);

    expect(await screen.findByText("Connected as Alex")).toBeInTheDocument();
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(put?.[0]).toBe("/api/athletes/ath-1/intervals");
    expect(JSON.parse(put?.[1].body)).toEqual({ api_key: "my-secret-key-123" });
    expect(screen.queryByDisplayValue("my-secret-key-123")).not.toBeInTheDocument();
    expect(screen.getByText("3 rides imported")).toBeInTheDocument();
  });

  it("explains a refused key", async () => {
    fetchMock.mockResolvedValueOnce(json(disconnected)).mockResolvedValueOnce(json({ detail: "Intervals.icu did not accept that API key" }, 400));
    renderCard();

    await userEvent.type(await screen.findByLabelText("API key"), "wrong-key-12345");
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));

    expect(await screen.findByText("Intervals.icu did not accept that API key")).toBeInTheDocument();
  });

  it("asks for a new key when the connection was paused", async () => {
    fetchMock.mockResolvedValueOnce(json({ ...connected, active: false }));
    renderCard();
    expect(await screen.findByText(/stopped accepting the key/)).toBeInTheDocument();
    expect(screen.getByLabelText("API key")).toBeInTheDocument();
  });

  it("disconnects only after confirmation", async () => {
    fetchMock.mockResolvedValueOnce(json(connected)).mockResolvedValueOnce(json({ ...connected, active: false }));
    renderCard();

    await userEvent.click(await screen.findByRole("button", { name: "Disconnect" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Disconnect" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(true));
  });
});
