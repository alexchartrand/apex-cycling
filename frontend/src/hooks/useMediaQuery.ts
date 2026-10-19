import { useSyncExternalStore } from "react";

/** Breakpoints shared with the CSS (see theme/tokens.css usage). */
export const PHONE_QUERY = "(max-width: 640px)";
export const COMPACT_SHELL_QUERY = "(max-width: 899px)";

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
