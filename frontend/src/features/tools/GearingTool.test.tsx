import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Bike } from "../equipment/types";
import { GearingTool } from "./GearingTool";
import { useToolInputs } from "./useToolInputs";

const gear = (id: string, chainring_teeth: number, cog_teeth: number) => ({
  id,
  bike_id: "b1",
  chainring_teeth,
  cog_teeth,
  rollout_mm: 2096,
  tire: null,
  ratio: 0,
  development_m: 0,
  gear_inches: 0,
});
const bikes: Bike[] = [{ id: "b1", name: "Track", weight_kg: 7.4, notes: null, gears: [gear("g1", 50, 15), gear("g2", 52, 14)] }];

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200 });
}

function Gearing() {
  return <GearingTool inputs={useToolInputs()} />;
}

describe("GearingTool saved gears", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/athletes/me")) return Promise.resolve(json({ id: "a1", user_id: "u1", display_name: "Rider" }));
        if (url.endsWith("/bikes")) return Promise.resolve(json(bikes));
        if (url.endsWith("/tracks")) return Promise.resolve(json([]));
        return Promise.resolve(json({}));
      }),
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("starts from the first saved gear, picks another, and None goes back to the typical gear", async () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/tools/gearing"]}>
          <Gearing />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const picker = await screen.findByLabelText("Saved gear");
    expect(picker).toHaveValue("g1");
    expect(screen.getByLabelText("Chainring")).toHaveValue("50");

    const user = userEvent.setup();
    await user.selectOptions(picker, "g2");
    expect(screen.getByLabelText("Chainring")).toHaveValue("52");
    expect(screen.getByLabelText("Cog")).toHaveValue("14");

    // 52×14 on 2.096 m is also the typical gear, yet the picker says None.
    await user.selectOptions(picker, "None");
    expect(picker).toHaveValue("none");
    expect(screen.getByLabelText("Chainring")).toHaveValue("52");
  });

  it("fills the rollout from a standard tire and shows which one a typed rollout is", async () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/tools/gearing"]}>
          <Gearing />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const preset = await screen.findByLabelText("Standard tire");
    await screen.findByLabelText("Saved gear");
    expect(preset).toHaveValue("700×23c");

    const user = userEvent.setup();
    await user.selectOptions(preset, "700×25c (2105 mm)");
    expect(screen.getByLabelText("Rollout")).toHaveValue("2.105");
    expect(preset).toHaveValue("700×25c");
  });
});
