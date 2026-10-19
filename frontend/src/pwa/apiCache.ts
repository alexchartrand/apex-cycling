/** Name of the workbox runtime cache for /api/athletes/* (see vite.config.ts). */
export const API_CACHE_NAME = "apex-api";

/** Drop cached athlete data so the next person on this device can't see it offline. */
export async function clearApiCache(): Promise<void> {
  if (typeof caches === "undefined") return;
  try {
    await caches.delete(API_CACHE_NAME);
  } catch {
    // Cache storage unavailable (private mode): nothing was cached anyway.
  }
}
