import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { groupBySession } from "./insights";
import { InsightRow } from "./InsightRow";
import { useInsightsFeed } from "./useInsights";
import "./Insights.css";

const MAX_SESSIONS = 3;
const MAX_PER_SESSION = 4;

/** Home: headlines from the last weeks of sessions, grouped by session. Hidden until there are some. */
export function WhatsNewCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("insights");
  const fmt = useFormat();
  const feed = useInsightsFeed(athleteId);
  if (!feed.data || feed.data.length === 0) return null;

  return (
    <Card title={t("whatsNew.title")} eyebrow={t("whatsNew.eyebrow")}>
      <ul className="whats-new">
        {groupBySession(feed.data)
          .slice(0, MAX_SESSIONS)
          .map((group) => (
            <li key={group.external_event_id} className="whats-new__session">
              <Link to={`/sessions/${group.external_event_id}`} className="whats-new__link">
                <span className="whats-new__date">{fmt.date(group.event_date, "dayMonth")}</span>
                <span className="whats-new__name">{group.session_name}</span>
              </Link>
              <div className="insights-banner__list">
                {group.insights.slice(0, MAX_PER_SESSION).map((insight) => (
                  <InsightRow key={insight.key} insight={insight} />
                ))}
              </div>
              {group.insights.length > MAX_PER_SESSION && (
                <Link to={`/sessions/${group.external_event_id}`} className="whats-new__more">
                  {t("whatsNew.more", { count: group.insights.length - MAX_PER_SESSION })}
                </Link>
              )}
            </li>
          ))}
      </ul>
    </Card>
  );
}
