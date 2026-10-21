import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/ui";
import { TrackSettingsDialog } from "./TrackSettingsDialog";
import type { TrackSummary } from "./types";

const track: TrackSummary = {
  id: "t1",
  name: "Tour complet",
  length_m: null,
  indoor: null,
  elevation_m: null,
  default_temp_c: null,
  sqorz_name: null,
  city: null,
  region: null,
  country: null,
  latitude: null,
  longitude: null,
  width_m: null,
  surface: null,
  bank_straight_deg: null,
  bank_curve_deg: null,
  notes: null,
  can_edit: true,
  loops: [
    { id: "l1", name: "Courbe 1", distance_m: null, hidden: true },
    { id: "l2", name: "Finish", distance_m: 250, hidden: false },
  ],
  views: [{ id: "v1", name: "200m", hidden: false }],
};

function renderDialog(onOpenChange = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TrackSettingsDialog track={track} open onOpenChange={onOpenChange} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return onOpenChange;
}

describe("TrackSettingsDialog", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(track), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("shows the saved checkpoint choices", () => {
    renderDialog();
    expect(screen.getByRole("checkbox", { name: "Courbe 1" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Finish/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "200m" })).toBeChecked();
  });

  it("saves the edited settings with a PATCH to the track", async () => {
    const onOpenChange = renderDialog();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Lap length"), "250");
    await user.selectOptions(screen.getByLabelText("Setting"), "indoor");
    await user.click(screen.getByRole("checkbox", { name: "Courbe 1" })); // show it again
    await user.click(screen.getByRole("checkbox", { name: "200m" })); // stop offering the view
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/tracks/t1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({
      length_m: 250,
      indoor: true,
      elevation_m: null,
      default_temp_c: null,
      hidden_loop_ids: [],
      hidden_view_ids: ["v1"],
    });
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("won't save a value the backend would reject", async () => {
    renderDialog();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Lap length"), "5000");
    expect(screen.getByText(/Enter a value between 1 and 1000/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("shows why a save failed and stays open", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: "Not allowed to edit this track" }), { status: 403 }));
    const onOpenChange = renderDialog();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You can't edit this track's settings.");
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });
});
