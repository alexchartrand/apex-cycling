// Same-origin by default: in dev the Vite server proxies /api to the backend
// (vite.config.ts), in prod the edge Caddy does (docker/Caddyfile). Set
// VITE_API_URL only to point a build at a backend on another origin.
const API_URL = `${import.meta.env.VITE_API_URL ?? ""}/api`;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Access tokens are short-lived by design (15 min); auth endpoints themselves
// are excluded from the retry-on-401 dance below so a wrong password doesn't
// burn an extra round trip (and rate-limit budget) attempting a pointless refresh.
const NO_REFRESH_RETRY_PATHS = new Set([
  "/auth/login",
  "/auth/signup",
  "/auth/refresh",
  "/auth/password-reset/request",
  "/auth/password-reset/check",
  "/auth/password-reset/confirm",
]);

// Shared across concurrent 401s so a burst of requests right after the access
// token expires triggers exactly one /auth/refresh call, not one per request.
let refreshInFlight: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

function doFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      // A FormData body needs the browser to set its own multipart boundary.
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
}

function detailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{ msg: "Value error, Password must…" }, …]
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") {
    return detail[0].msg.replace(/^Value error, /, "");
  }
  return fallback;
}

/** Like `apiFetch`, but hands back the raw successful Response (for downloads). */
export async function apiRequest(path: string, init?: RequestInit): Promise<Response> {
  let response = await doFetch(path, init);

  if (response.status === 401 && !NO_REFRESH_RETRY_PATHS.has(path)) {
    const refreshed = await refreshSession();
    if (refreshed) {
      response = await doFetch(path, init);
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, detailMessage(body.detail, response.statusText));
  }
  return response;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiRequest(path, init);

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
