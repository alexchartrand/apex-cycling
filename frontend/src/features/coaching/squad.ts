import type { SquadRow } from "./types";

/** "+0.35" style gap to the fastest, in milliseconds; the leader (or an athlete without a time) has none to show. */
export function gapToShow(row: SquadRow): number | null {
  return row.gap_ms != null && row.gap_ms > 0 ? row.gap_ms : null;
}

/** Athletes with a time first (already ranked by the server), then those without. */
export function splitSquad(rows: SquadRow[]): { ranked: SquadRow[]; unranked: SquadRow[] } {
  return { ranked: rows.filter((row) => row.time_ms != null), unranked: rows.filter((row) => row.time_ms == null) };
}

/** Compliance as a whole percentage, or null when nothing was due. */
export function compliancePercent(compliance: number | null): number | null {
  return compliance == null ? null : Math.round(compliance * 100);
}
