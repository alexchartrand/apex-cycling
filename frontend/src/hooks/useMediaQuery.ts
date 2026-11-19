import { useSyncExternalStore } from "react";

/**
 * The app's only three breakpoints, the same numbers the CSS uses (custom
 * properties can't go in a media query, so they're written out there; see the
 * note at the top of theme/tokens.css): phone ≤ 640px, compact shell (bottom
 * tabs, no sidebar) ≤ 899px, wide ≥ 1100px.
 */
export const PHONE_QUERY = "(max-width: 640px)";
export const COMPACT_SHELL_QUERY = "(max-width: 899px)";
export const WIDE_QUERY = "(min-width: 1100px)";

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window.matchMedia !== "function") return () => {};
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    () => typeof window.matchMedia === "function" && window.matchMedia(query).matches,
    () => false,
  );
}
