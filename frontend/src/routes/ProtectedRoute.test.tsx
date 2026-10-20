import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "../theme/ThemeProvider";
import { ProtectedRoute } from "./ProtectedRoute";

function LoginProbe() {
  const from = (useLocation().state as { from?: string } | null)?.from;
  return <p>login, then back to: {from}</p>;
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401 })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a signed-out visitor to login and remembers the whole address, fragment included", async () => {
    // An invitation link carries its token in the fragment: losing it would lose the invitation.
    render(
      <ThemeProvider>
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <MemoryRouter initialEntries={["/join?ref=mail#token=abc123"]}>
            <Routes>
              <Route path="/login" element={<LoginProbe />} />
              <Route element={<ProtectedRoute />}>
                <Route path="/join" element={<p>join page</p>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </ThemeProvider>,
    );
    expect(await screen.findByText("login, then back to: /join?ref=mail#token=abc123")).toBeInTheDocument();
  });
});
