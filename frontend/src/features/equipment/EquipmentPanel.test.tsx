import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../../components/ui";
import { EquipmentPanel } from "./EquipmentPanel";
import { STANDARD_TIRES } from "./gear";
import { GearPicker } from "./GearPicker";
import type { Bike } from "./types";

const bike: Bike = {
  id: "b1",
  name: "Track bike",
  weight_kg: 7.4,
  notes: null,
  tire: "Veloflex",
  crr: null,
  gears: [
    { id: "g1", bike_id: "b1", chainring_teeth: 50, cog_teeth: 15, rollout_mm: 2100, ratio: 3.33, development_m: 7, gear_inches: 104.9 },
  ],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function wrap(children: React.ReactNode) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter>{children}</MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

describe("EquipmentPanel", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockImplementation((_url: string, init?: RequestInit) =>
      Promise.resolve(init?.method === "POST" ? json({ id: "g2" }, 201) : json([bike])),
    );
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists the bikes with their tire, and each gear's name and what it rolls", async () => {
    render(wrap(<EquipmentPanel athleteId="a1" />));
    expect(await screen.findByText("Track bike")).toBeInTheDocument();
    expect(screen.getByText("50×15")).toBeInTheDocument();
    expect(screen.getByText(/7\.00 m per turn/)).toBeInTheDocument();
    expect(screen.getByText(/Veloflex/)).toBeInTheDocument();
  });

  it("adds a gear to a bike with the numbers typed", async () => {
    render(wrap(<EquipmentPanel athleteId="a1" />));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Add a gear" }));

    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled(); // no teeth yet
    await user.type(screen.getByLabelText("Chainring"), "52");
    await user.type(screen.getByLabelText("Cog"), "14");
    expect(screen.getByLabelText(/Rollout/)).toHaveValue(2096);
    await user.click(save);

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const [url, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "POST")!;
    expect(url).toBe("/api/athletes/a1/bikes/b1/gears");
    expect(JSON.parse(init.body)).toEqual({ chainring_teeth: 52, cog_teeth: 14, rollout_mm: 2096 });
  });

  it("fills a bike's tire and its Crr from the list, and still takes a tire that isn't listed", async () => {
    render(wrap(<EquipmentPanel athleteId="a1" />));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Add a bike" }));
    await user.type(screen.getByLabelText("Name"), "Spare");

    const listed = STANDARD_TIRES[0];
    await user.selectOptions(screen.getByLabelText("Tire from the list"), listed.label);
    expect(screen.getByLabelText("Tire")).toHaveValue(listed.label);
    expect(screen.getByLabelText(/^Crr/)).toHaveValue(listed.crr);

    await user.clear(screen.getByLabelText("Tire"));
    await user.type(screen.getByLabelText("Tire"), "Home-made 22");
    expect(screen.getByLabelText("Tire from the list")).toHaveValue("");
    await user.clear(screen.getByLabelText(/^Crr/));
    await user.type(screen.getByLabelText(/^Crr/), "0.5");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled(); // Crr out of range
    await user.clear(screen.getByLabelText(/^Crr/));
    await user.type(screen.getByLabelText(/^Crr/), "0.0035");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const [, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "POST")!;
    expect(JSON.parse(init.body)).toMatchObject({ tire: "Home-made 22", crr: 0.0035 });
  });

  it("refuses a chainring outside the allowed range", async () => {
    render(wrap(<EquipmentPanel athleteId="a1" />));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Add a gear" }));
    await user.type(screen.getByLabelText("Chainring"), "5");
    await user.type(screen.getByLabelText("Cog"), "14");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });
});

describe("GearPicker", () => {
  it("offers every gear and reports the pick; the empty choice clears", async () => {
    const onChange = vi.fn().mockResolvedValue(undefined);
    render(wrap(<GearPicker bikes={[bike]} value={null} onChange={onChange} label="Gear" emptyLabel="No gear" />));
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Gear"), "Track bike · 50×15");
    expect(onChange).toHaveBeenLastCalledWith("g1");
    await user.selectOptions(screen.getByLabelText("Gear"), "No gear");
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it("points to Settings when there is no bike yet", () => {
    render(wrap(<GearPicker bikes={[]} value={null} onChange={vi.fn()} label="Gear" emptyLabel="No gear" />));
    expect(screen.getByRole("link")).toHaveAttribute("href", "/equipment");
  });
});
