import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AthleteScopeContext, coachAthletePath, useAthletePath, useCanEdit } from "./athleteScope";

const scoped = ({ children }: { children: React.ReactNode }) => (
  <AthleteScopeContext.Provider value={{ athleteId: "a 1", basePath: coachAthletePath("a 1") }}>{children}</AthleteScopeContext.Provider>
);

describe("athlete scope", () => {
  it("leaves links and edits alone outside a coach's view", () => {
    expect(renderHook(() => useAthletePath()).result.current("/sessions/e1")).toBe("/sessions/e1");
    expect(renderHook(() => useCanEdit()).result.current).toBe(true);
  });

  it("keeps links inside the coached athlete and makes their data read-only", () => {
    expect(renderHook(() => useAthletePath(), { wrapper: scoped }).result.current("/sessions/e1?tab=comments")).toBe(
      "/coach/athletes/a%201/sessions/e1?tab=comments",
    );
    expect(renderHook(() => useCanEdit(), { wrapper: scoped }).result.current).toBe(false);
  });
});
