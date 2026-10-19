export type SortDirection = "asc" | "desc";
export type SortValue = number | string | null | undefined;

/**
 * Stable sort by an extracted value. Missing values (null/undefined/NaN)
 * always sink to the bottom regardless of direction, so a lap with a missed
 * checkpoint never shows up as the "fastest" when sorting ascending.
 */
export function sortRows<T>(rows: readonly T[], getValue: (row: T) => SortValue, direction: SortDirection): T[] {
  const sign = direction === "asc" ? 1 : -1;
  return rows
    .map((row, index) => ({ row, index, value: getValue(row) }))
    .sort((a, b) => {
      const aMissing = isMissing(a.value);
      const bMissing = isMissing(b.value);
      if (aMissing || bMissing) {
        if (aMissing && bMissing) return a.index - b.index;
        return aMissing ? 1 : -1;
      }
      const cmp =
        typeof a.value === "number" && typeof b.value === "number"
          ? a.value - b.value
          : String(a.value).localeCompare(String(b.value), undefined, { numeric: true });
      return cmp !== 0 ? cmp * sign : a.index - b.index;
    })
    .map((entry) => entry.row);
}

function isMissing(value: SortValue): boolean {
  return value == null || (typeof value === "number" && Number.isNaN(value));
}

/** Header click cycle: unsorted → asc → desc → unsorted. */
export function nextSort(
  current: { columnId: string; direction: SortDirection } | null,
  columnId: string,
): { columnId: string; direction: SortDirection } | null {
  if (current?.columnId !== columnId) return { columnId, direction: "asc" };
  if (current.direction === "asc") return { columnId, direction: "desc" };
  return null;
}
