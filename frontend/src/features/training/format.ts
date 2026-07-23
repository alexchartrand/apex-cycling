export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  const totalSeconds = ms / 1000;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds - minutes * 60;
  const secondsStr = seconds.toFixed(3).padStart(6, "0");
  return `${minutes}:${secondsStr}`;
}
