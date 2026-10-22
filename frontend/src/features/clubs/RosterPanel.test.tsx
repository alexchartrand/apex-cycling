import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../../components/ui";
import { RosterPanel } from "./RosterPanel";
import type { Club, RosterAthlete } from "./types";

const club: Club = { id: "c1", name: "CNCB", slug: "cncb", timezone: "UTC", role: "coach" };

const rider = (name: string, category: string | null): RosterAthlete => ({
  id: name,
  display_name: name,
  user_id: null,
  managed: true,
  birthdate: null,
  sex: null,
  category,
});
const roster = [rider("Cleo", "M30"), rider("Ann", "U19"), rider("Bob", "U19"), rider("Dan", null)];

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });

describe("RosterPanel", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => Promise.resolve(json(url.endsWith("/athletes") ? roster : url.includes("coach-links") ? [] : {}))),
    );
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ToastProvider>
          <TooltipProvider>
            <MemoryRouter>
              <RosterPanel club={club} />
            </MemoryRouter>
          </TooltipProvider>
        </ToastProvider>
      </QueryClientProvider>,
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  const names = () => within(screen.getByRole("table")).getAllByRole("row").slice(1).map((row) => within(row).getAllByRole("cell")[0].textContent);

  it("shows each athlete's age category and filters by it, youngest category first", async () => {
    await screen.findByText("Ann");
    expect(names()).toHaveLength(4);

    const filter = screen.getByLabelText("Age category");
    expect(within(filter).getAllByRole("option").map((o) => o.textContent)).toEqual(["All ages", "Junior (U19)", "Master 30–34"]);

    await userEvent.setup().selectOptions(filter, "U19");
    expect(names().sort()).toEqual(["Ann", "Bob"]);
  });
});
