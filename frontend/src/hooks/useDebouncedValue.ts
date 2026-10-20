import { useEffect, useState } from "react";

/** `value`, once it has stopped changing for `delayMs` (compared by JSON, so a new but equal object doesn't restart it). */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [settled, setSettled] = useState(value);
  const key = JSON.stringify(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(JSON.parse(key) as T), delayMs);
    return () => clearTimeout(timer);
  }, [key, delayMs]);
  return settled;
}
