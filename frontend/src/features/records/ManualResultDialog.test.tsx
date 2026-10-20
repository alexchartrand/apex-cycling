import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/ui";
import type { TrackSummary } from "../training/types";
import { ManualResultDialog } from "./ManualResultDialog";

const tracks: TrackSummary[] = [
  { id: "t1", name: "Tour complet", length_m: 250, indoor: true, elevation_m: null, default_temp_c: null, can_edit: false, loops: [], views: [] },
];

function renderDialog(onClose = vi.fn(), trackList = tracks) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <ToastProvider>
        <ManualResultDialog athleteId="a1" tracks={trackList} result={null} onClose={onClose} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return onClose;
}

describe("ManualResultDialog", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("posts the result for a known track", async () => {
    const onClose = renderDialog();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Time"), "1:12.345");
    await user.selectOptions(screen.getByLabelText("Event"), "1km");
    await user.click(screen.getByRole("checkbox", { name: /race or competition/i }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/athletes/a1/manual-results");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toMatchObject({
      event_key: "1km",
      start_type: "standing",
      time_ms: 72_345,
      track_id: "t1",
      venue: null,
      is_competition: true,
    });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("explains a bad time instead of sending it", async () => {
    renderDialog();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Time"), "fast");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/Enter a time like 36.5/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("asks for a venue when there's no track to pick, and a 200 is only flying", async () => {
    renderDialog(vi.fn(), []);
    const user = userEvent.setup();
    expect(screen.getByLabelText("Venue")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Time"), "36.5");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Name the venue.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    await user.selectOptions(screen.getByLabelText("Event"), "f200");
    const start = screen.getByLabelText("Start");
    expect(start).toBeDisabled();
    expect(start).toHaveValue("flying");
  });
});
