import { describe, expect, it } from "vitest";
import { ApiError } from "./client";
import { errorMessage } from "./errors";

describe("errorMessage", () => {
  it("prefers a status-specific message", () => {
    expect(errorMessage(new ApiError(401, "Invalid email or password"), { 401: "Wrong password" })).toBe("Wrong password");
  });

  it("falls back to the backend detail", () => {
    expect(errorMessage(new ApiError(409, "Transponder already assigned"))).toBe("Transponder already assigned");
  });

  it("explains unreachable servers", () => {
    expect(errorMessage(new TypeError("Failed to fetch"))).toMatch(/reach the server/);
  });

  it("has a generic fallback", () => {
    expect(errorMessage(new Error("boom"))).toMatch(/Something went wrong/);
  });
});
