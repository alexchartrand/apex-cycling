import { describe, expect, it } from "vitest";
import { inviteState } from "./inviteState";

const NOW = new Date("2026-10-19T12:00:00Z");
const invite = (over: Partial<Parameters<typeof inviteState>[0]> = {}) => ({
  expires_at: "2026-11-01T00:00:00Z",
  max_uses: 5,
  use_count: 0,
  ...over,
});

describe("inviteState", () => {
  it("is active until it expires or is used up", () => {
    expect(inviteState(invite(), NOW)).toBe("active");
    expect(inviteState(invite({ max_uses: null, use_count: 500 }), NOW)).toBe("active");
    expect(inviteState(invite({ use_count: 4 }), NOW)).toBe("active");
  });

  it("is expired at and after its expiry, whatever the uses", () => {
    expect(inviteState(invite({ expires_at: "2026-10-19T12:00:00Z" }), NOW)).toBe("expired");
    expect(inviteState(invite({ expires_at: "2026-10-01T00:00:00Z", use_count: 5 }), NOW)).toBe("expired");
  });

  it("is used up once the uses reach the limit", () => {
    expect(inviteState(invite({ use_count: 5 }), NOW)).toBe("used_up");
    expect(inviteState(invite({ max_uses: 1, use_count: 1 }), NOW)).toBe("used_up");
  });
});
