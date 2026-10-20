const TOKEN_PATTERN = /^[A-Za-z0-9_-]{20,200}$/;

/** "#token=abc" (the invite link's fragment) → "abc", or "" when there isn't one. */
export function tokenFromHash(hash: string): string {
  const token = new URLSearchParams(hash.replace(/^#/, "")).get("token") ?? "";
  return TOKEN_PATTERN.test(token) ? token : "";
}

/** What someone pastes to join: the whole link, or just the token. "" when it's neither. */
export function tokenFromPasted(text: string): string {
  const trimmed = text.trim();
  if (TOKEN_PATTERN.test(trimmed)) return trimmed;
  const hashAt = trimmed.indexOf("#");
  return hashAt >= 0 ? tokenFromHash(trimmed.slice(hashAt)) : "";
}

/** The path the SPA uses to accept an invite; the token stays in the fragment so it never reaches a server log. */
export function joinPath(token: string): string {
  return `/join#token=${token}`;
}
