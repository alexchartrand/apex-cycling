import { describe, expect, it } from "vitest";
import { failedPasswordRules, isPasswordStrong } from "./passwordPolicy";

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
