import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import type { Language } from "../../i18n/language";
import { useLanguage } from "../../i18n/useLanguage";
import type { ThemeMode } from "../../theme/theme";
import { useTheme } from "../../theme/useTheme";
import { updatePreferences } from "./api";
import type { Preferences, User } from "./types";
import { CURRENT_USER_KEY } from "./useAuth";

/**
 * Language and theme live in localStorage (instant, works logged out and
 * offline); the user's account is the cross-device copy. These setters
 * change the device right away and, when someone is logged in, save it to
 * the account too.
 */
export function usePreferenceSetters() {
  const queryClient = useQueryClient();
  const { setLanguage } = useLanguage();
  const { setMode } = useTheme();
  const save = useMutation({
    mutationFn: (payload: Preferences) => updatePreferences(payload),
    onSuccess: (user) => queryClient.setQueryData(CURRENT_USER_KEY, user),
  });
  const { mutate } = save;

  const persist = useCallback(
    (payload: Preferences) => {
      // getQueryData, not useCurrentUser(): the switchers also sit on the
      // login page, which must not trigger a /auth/me fetch.
      if (queryClient.getQueryData<User | null>(CURRENT_USER_KEY)) mutate(payload);
    },
    [queryClient, mutate],
  );

  return {
    setLanguage: useCallback(
      (locale: Language) => {
        setLanguage(locale);
        persist({ locale });
      },
      [setLanguage, persist],
    ),
    setTheme: useCallback(
      (theme: ThemeMode) => {
        setMode(theme);
        persist({ theme });
      },
      [setMode, persist],
    ),
  };
}

/** Applies the account's saved preferences once per logged-in user. */
export function useApplyAccountPreferences(user: User | null | undefined) {
  const { setLanguage } = useLanguage();
  const { setMode } = useTheme();
  const appliedFor = useRef<string | null>(null);

  useEffect(() => {
    if (!user || appliedFor.current === user.id) return;
    appliedFor.current = user.id;
    if (user.locale) setLanguage(user.locale);
    if (user.theme) setMode(user.theme);
  }, [user, setLanguage, setMode]);
}
