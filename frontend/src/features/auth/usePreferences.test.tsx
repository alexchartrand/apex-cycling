import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import { ThemeProvider } from "../../theme/ThemeProvider";
import { useTheme } from "../../theme/useTheme";
import type { User } from "./types";
import { CURRENT_USER_KEY } from "./useAuth";
import { useApplyAccountPreferences, usePreferenceSetters } from "./usePreferences";

const user: User = { id: "u1", email: "a@b.c", is_platform_admin: false, locale: "fr", theme: "dark" };

function setup() {
  const queryClient = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
  return { queryClient, wrapper };
}

describe("account preferences", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    fetchMock.mockResolvedValue(new Response(JSON.stringify(user), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(async () => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    await i18n.changeLanguage("en");
  });

  it("applies the account's saved language and theme once per user", async () => {
    const { wrapper } = setup();
    const { result, rerender } = renderHook(
      ({ u }) => {
        useApplyAccountPreferences(u);
        return useTheme();
      },
      { wrapper, initialProps: { u: user as User | null } },
    );

    await waitFor(() => expect(result.current.mode).toBe("dark"));
    expect(i18n.language).toBe("fr");

    // A local change afterwards isn't overridden by a re-render with the same user.
    act(() => result.current.setMode("light"));
    rerender({ u: { ...user } });
    expect(result.current.mode).toBe("light");
  });

  it("leaves the device's choice alone when the account has none", () => {
    const { wrapper } = setup();
    const { result } = renderHook(
      () => {
        useApplyAccountPreferences({ ...user, locale: null, theme: null });
        return useTheme();
      },
      { wrapper },
    );
    expect(result.current.mode).toBe("system");
    expect(i18n.language).toBe("en");
  });

  it("saves changes to the account only when logged in", async () => {
    const { queryClient, wrapper } = setup();
    const { result } = renderHook(() => usePreferenceSetters(), { wrapper });

    act(() => result.current.setTheme("dark"));
    expect(fetchMock).not.toHaveBeenCalled();

    queryClient.setQueryData(CURRENT_USER_KEY, user);
    act(() => result.current.setTheme("light"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/me/preferences");
    expect(JSON.parse(init.body)).toEqual({ theme: "light" });
  });
});
