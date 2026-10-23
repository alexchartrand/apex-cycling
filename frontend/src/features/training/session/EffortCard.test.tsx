import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EffortCard } from "./EffortCard";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider, TooltipProvider } from "../../../components/ui";
import type { Effort } from "../types";

const effort: Effort = {
  index: 1,
  track_id: "t1",
  track_name: "Bromont",
  label: null,
  start_time: "2026-07-07T13:00:00Z",
  start_type: "standing",
  lap_ids: ["l1", "l2", "l3", "l4", "l5"],
  completed_lap_count: 5,
  lap_times_ms: [26_000, 20_000, 20_200, 20_400, 20_600],
  total_time_ms: 107_200,
  best_lap_ms: 20_000,
  distance_m: 1250,
  avg_speed_kmh: 42,
  half_lap_splits: [],
  pacing: { reference_lap_count: 4, even_pace_ms: 20_300, cv_pct: 1.2, fade_pct: 3.0, deviations_pct: [28, -1.5, -0.5, 0.5, 1.5], start_lap_skipped: true },
  peak_speed_kmh: 61.2,
  peak_speed_lap_id: "l2",
  launch_time_ms: 8_000,
  launch_distance_m: 50,
  launch_accel_ms2: 1.6,
};

function renderCard(over: Partial<Effort> = {}) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter>
            <EffortCard athleteId="a1" eventId="evt1" effort={{ ...effort, ...over }} bikes={[]} />
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("EffortCard sprint and pacing", () => {
  it("shows top speed, launch, lap spread and fade", () => {
    renderCard();
    expect(screen.getByText("Top speed")).toBeInTheDocument();
    expect(screen.getByText("61.2")).toBeInTheDocument();
    expect(screen.getByText("Launch")).toBeInTheDocument();
    expect(screen.getByText(/To the first checkpoint, 50 m · avg 1\.6 m\/s²/)).toBeInTheDocument();
    expect(screen.getByText("Lap spread")).toBeInTheDocument();
    expect(screen.getByText("+3.0")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Pacing" })).toBeInTheDocument();
  });

  it("offers a link to compare the effort", () => {
    renderCard();
    expect(screen.getByRole("link", { name: "Compare with another effort" })).toHaveAttribute("href", "/compare?a=evt1&ae=l1");
  });

  it("hides what the data can't give", () => {
    renderCard({ pacing: null, peak_speed_kmh: null, launch_accel_ms2: null, launch_time_ms: null, launch_distance_m: null });
    expect(screen.queryByText("Top speed")).not.toBeInTheDocument();
    expect(screen.queryByText("Lap spread")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Pacing" })).not.toBeInTheDocument();
  });
});
