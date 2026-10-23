import type { Insight } from "./types";

/** How far back "What's new" looks, and how many headlines it asks for. */
export const FEED_DAYS = 30;
export const FEED_LIMIT = 30;

export interface SessionInsights {
  external_event_id: string;
  session_name: string;
  event_date: string;
  insights: Insight[];
}

/** The feed grouped by session, in the order the sessions first appear (newest first). */
export function groupBySession(insights: Insight[]): SessionInsights[] {
  const groups = new Map<string, SessionInsights>();
  for (const insight of insights) {
    const group = groups.get(insight.external_event_id);
    if (group) group.insights.push(insight);
    else
      groups.set(insight.external_event_id, {
        external_event_id: insight.external_event_id,
        session_name: insight.session_name,
        event_date: insight.event_date,
        insights: [insight],
      });
  }
  return [...groups.values()];
}

/** The headlines in `after` that weren't in `before`. */
export function newInsights(before: Insight[], after: Insight[]): Insight[] {
  const known = new Set(before.map((insight) => insight.key));
  return after.filter((insight) => !known.has(insight.key));
}

/** Time saved over the previous best, in ms (positive = faster), when both are known. */
export function improvementMs(insight: Insight): number | null {
  return insight.time_ms != null && insight.previous_ms != null ? insight.previous_ms - insight.time_ms : null;
}
