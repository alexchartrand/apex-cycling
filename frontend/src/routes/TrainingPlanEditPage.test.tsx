import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TooltipProvider } from "../components/ui";
import { TrainingPlanEditPage } from "./TrainingPlanEditPage";

vi.mock("../features/athletes/useActiveAthlete", () => ({ useActiveAthlete: () => ({ data: { id: "a1" } }) }));

const phase = { kind: "base", name: null, start: "2026-11-23", end: "2027-02-14", focus: null, hours: null };

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function renderAt(url: string) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TooltipProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[url]}>
            <Routes>
              <Route path="/plans/new" element={<TrainingPlanEditPage />} />
              <Route path="*" element={<Where />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe("TrainingPlanEditPage ?ai=", () => {
  const fetchMock = vi.fn();
  const posted = (path: string) =>
    fetchMock.mock.calls.filter(([url, init]) => String(url).endsWith(path) && init?.method === "POST").map(([, init]) => JSON.parse(init.body));

  beforeEach(() => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/suggest-phases")) return Promise.resolve(new Response(JSON.stringify([phase])));
      if (url.endsWith("/training-plans") && init?.method === "POST") return Promise.resolve(new Response(JSON.stringify({ id: "p9" }), { status: 201 }));
      return Promise.resolve(new Response("[]"));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("asks the plan's questions, saves it with suggested phases, then opens the AI coach's intake on it", async () => {
    renderAt("/plans/new?ai=chat");
    expect(screen.getByRole("heading", { name: "Build a plan with the AI coach" })).toBeInTheDocument();
    expect(screen.queryByText("Phases")).toBeNull();

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Gran fondo 2027" } });
    fireEvent.change(screen.getByLabelText("Sport"), { target: { value: "cycling" } });
    fireEvent.change(screen.getByLabelText("Goal"), { target: { value: "Ride 160 km under 6 h" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue with the AI coach" }));

    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/ai-coach?tab=chat&build=p9"));
    const [plan] = posted("/training-plans");
    expect(plan).toMatchObject({ name: "Gran fondo 2027", sport: "cycling", goal_text: "Ride 160 km under 6 h", phases: [phase] });
  });

  it("goes back to where it came from", () => {
    renderAt("/plans/new?ai=chat");
    expect(screen.getByRole("link", { name: /AI coach/ })).toHaveAttribute("href", "/ai-coach?tab=chat");
  });
});
