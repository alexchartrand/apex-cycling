import { describe, expect, it } from "vitest";
import { joinPath, tokenFromHash, tokenFromPasted } from "./inviteToken";

const TOKEN = "q3Zr8a-1X_Lm0pTYb7nHc2VdE5uKfGiJ9sWoA4xRNkU";

describe("tokenFromHash", () => {
  it("reads the token out of the fragment", () => {
    expect(tokenFromHash(`#token=${TOKEN}`)).toBe(TOKEN);
  });

  it("is empty for anything else", () => {
    expect(tokenFromHash("")).toBe("");
    expect(tokenFromHash("#")).toBe("");
    expect(tokenFromHash("#other=1")).toBe("");
    expect(tokenFromHash("#token=short")).toBe("");
    expect(tokenFromHash("#token=<script>alert(1)</script>")).toBe("");
  });
});

describe("tokenFromPasted", () => {
  it("accepts the whole link, with or without a path prefix or surrounding space", () => {
    expect(tokenFromPasted(`https://apex.example.com/join#token=${TOKEN}`)).toBe(TOKEN);
    expect(tokenFromPasted(`  http://localhost:5173/join#token=${TOKEN}\n`)).toBe(TOKEN);
  });

  it("accepts the bare token", () => {
    expect(tokenFromPasted(` ${TOKEN} `)).toBe(TOKEN);
  });

  it("rejects text that is neither", () => {
    expect(tokenFromPasted("")).toBe("");
    expect(tokenFromPasted("hello there")).toBe("");
    expect(tokenFromPasted("https://apex.example.com/join")).toBe("");
  });
});

describe("joinPath", () => {
  it("keeps the token in the fragment", () => {
    expect(joinPath(TOKEN)).toBe(`/join#token=${TOKEN}`);
    expect(tokenFromHash(joinPath(TOKEN).slice(joinPath(TOKEN).indexOf("#")))).toBe(TOKEN);
  });
});
