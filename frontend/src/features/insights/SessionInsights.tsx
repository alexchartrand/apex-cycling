import { useTranslation } from "react-i18next";
import { InsightRow } from "./InsightRow";
import { useSessionInsights } from "./useInsights";
import "./Insights.css";

/** The headlines of one session, as a banner above its tabs. Nothing when there are none. */
export function SessionInsights({ athleteId, eventId }: { athleteId: string; eventId: string }) {
  const { t } = useTranslation("insights");
  const insights = useSessionInsights(athleteId, eventId);
  if (!insights.data || insights.data.length === 0) return null;
  return (
    <section className="insights-banner" aria-label={t("banner")}>
      <h2 className="insights-banner__title">{t("banner")}</h2>
      <div className="insights-banner__list">
        {insights.data.map((insight) => (
          <InsightRow key={insight.key} insight={insight} />
        ))}
      </div>
    </section>
  );
}
