export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  // Round to whole ms before splitting, so e.g. an averaged 59999.6 ms
  // becomes 1:00.000 rather than 0:60.000.
  const totalMs = Math.round(ms);
  const minutes = Math.floor(totalMs / 60_000);
  const secondsStr = ((totalMs - minutes * 60_000) / 1000).toFixed(3).padStart(6, "0");
  return `${minutes}:${secondsStr}`;
}

export function formatKm(km: number): string {
  return `${km.toFixed(2)} km`;
}
