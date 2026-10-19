import { beforeEach, describe, expect, it } from "vitest";
import { readStoredThemeMode, resolveTheme, storeThemeMode, THEME_STORAGE_KEY } from "./theme";

describe("resolveTheme", () => {
  it("follows the system preference in system mode", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });

  it("ignores the system preference when forced", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});

describe("stored theme mode", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to system when nothing or garbage is stored", () => {
    expect(readStoredThemeMode()).toBe("system");
    localStorage.setItem(THEME_STORAGE_KEY, "sepia");
    expect(readStoredThemeMode()).toBe("system");
  });

  it("round-trips a stored mode", () => {
    storeThemeMode("dark");
    expect(readStoredThemeMode()).toBe("dark");
  });
});
