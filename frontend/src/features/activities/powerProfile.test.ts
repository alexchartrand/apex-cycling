import { beforeEach, describe, expect, it } from "vitest";
import { dismiss, fitIsTrustworthy, isDismissed, suggestedFtp, wPrimeKj } from "./powerProfile";
import type { PowerProfile } from "./types";

const profile = (over: Partial<PowerProfile> = {}): PowerProfile => ({
  days: 90,
  critical_power: { cp_w: 300, w_prime_j: 20000, r_squared: 0.995, points: 5 },
  ftp_current_w: 270,
  ftp_suggestion: { ftp_w: 284.6, source_duration_s: 1200, source_activity_id: "a", source_power_w: 299.6 },
  ...over,
});

describe("powerProfile", () => {
  beforeEach(() => localStorage.clear());

  it("rounds the suggestion to whole watts", () => {
    expect(suggestedFtp(profile())).toBe(285);
    expect(suggestedFtp(profile({ ftp_suggestion: null }))).toBeNull();
    expect(suggestedFtp(undefined)).toBeNull();
  });

  it("remembers a dismissal for that rider and value only", () => {
    expect(isDismissed("r1", 285)).toBe(false);
    dismiss("r1", 285);
    expect(isDismissed("r1", 285)).toBe(true);
    expect(isDismissed("r1", 290)).toBe(false);
    expect(isDismissed("r2", 285)).toBe(false);
  });

  it("converts W′ to kilojoules", () => {
    expect(wPrimeKj(20000)).toBe(20);
  });

  it("only trusts a tight fit over enough efforts", () => {
    expect(fitIsTrustworthy(profile())).toBe(true);
    expect(fitIsTrustworthy(profile({ critical_power: { cp_w: 300, w_prime_j: 20000, r_squared: 0.9, points: 5 } }))).toBe(false);
    expect(fitIsTrustworthy(profile({ critical_power: null }))).toBe(false);
  });
});
