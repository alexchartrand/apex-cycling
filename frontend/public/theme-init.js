// Set the theme before first paint so dark-mode users don't get a flash of
// the paper theme. Mirrors theme/theme.ts (same storage key). Kept as a file
// (not inline in index.html) so the CSP can forbid inline scripts.
(function () {
  try {
    var mode = localStorage.getItem("apex-theme");
    var dark = mode === "dark" || (mode !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  } catch {}
})();
