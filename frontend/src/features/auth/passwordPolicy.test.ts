import { describe, expect, it } from "vitest";
import { failedPasswordRules, isNewPasswordReady, isPasswordStrong } from "./passwordPolicy";

describe("failedPasswordRules", () => {
  it("flags short passwords", () => {
    expect(failedPasswordRules("Ab1!")).toEqual(["length"]);
  });

  it("flags passwords with too few character classes", () => {
    expect(failedPasswordRules("alllowercaseletters")).toEqual(["classes"]);
  });

  it("accepts 12+ chars with 3 classes", () => {
    expect(failedPasswordRules("Correcthorse123")).toEqual([]);
    expect(isPasswordStrong("Correcthorse123")).toBe(true);
  });
});

describe("isNewPasswordReady", () => {
  it("needs a strong password that the confirmation repeats", () => {
    expect(isNewPasswordReady("Correcthorse123!", "Correcthorse123!")).toBe(true);
    expect(isNewPasswordReady("Correcthorse123!", "Correcthorse123")).toBe(false);
    expect(isNewPasswordReady("short", "short")).toBe(false);
  });
});
