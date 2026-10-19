import { CalendarDays, ChevronRight, CloudDownload } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, ButtonLink, Card, EmptyState, PageHeader, SkeletonGroup } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { groupByMonth } from "../features/training/sessionStats";
import { useSessions } from "../features/training/useTraining";
import { parseLocalDate } from "../i18n/format";
import { useFormat } from "../i18n/useFormat";
import "./LogPage.css";

export function LogPage() {
  const { t } = useTranslation(["training", "shell", "common"]);
  const fmt = useFormat();
  const athlete = useActiveAthlete();
  const sessions = useSessions(athlete.data?.id ?? "");
  const monthFormat = new Intl.DateTimeFormat(fmt.locale, { month: "long", year: "numeric" });

  return (
    <>
      <PageHeader
        title={t("log.title")}
        description={t("log.description")}
        actions={
          <ButtonLink to="/import" variant="secondary" icon={<CloudDownload aria-hidden />}>
            {t("shell:nav.import")}
          </ButtonLink>
        }
      />

      {(athlete.isLoading || sessions.isLoading) && <SkeletonGroup lines={6} />}
      {(athlete.isError || sessions.isError) && <p role="alert">{t("log.loadError")}</p>}

      {sessions.data?.length === 0 && (
        <EmptyState
          icon={<CalendarDays aria-hidden />}
          title={t("log.emptyTitle")}
          description={t("log.emptyDescription")}
          action={
            <ButtonLink to="/import">{t("log.emptyAction")}</ButtonLink>
          }
        />
      )}

      <div className="log">
        {sessions.data &&
          groupByMonth(sessions.data).map((group) => (
            <section key={group.month} className="log__month">
              <h2 className="log__month-title eyebrow">{monthFormat.format(parseLocalDate(`${group.month}-01`))}</h2>
              <Card padding="flush">
                <ul className="log__list">
                  {group.sessions.map((session) => {
                    const date = parseLocalDate(session.event_date);
                    return (
                      <li key={session.external_event_id}>
                        <Link to={`/sessions/${session.external_event_id}`} className="log__row">
                          <span className="log__date">
                            <span className="log__day">{date.getDate()}</span>
                            <span className="log__weekday">
                              {new Intl.DateTimeFormat(fmt.locale, { weekday: "short" }).format(date)}
                            </span>
                          </span>
                          <span className="log__main">
                            <span className="log__name">{session.event_name}</span>
                            <span className="log__tracks">
                              {session.track_names.map((name) => (
                                <Badge key={name}>{name}</Badge>
                              ))}
                            </span>
                          </span>
                          <span className="log__laps">{t("log.laps", { count: session.lap_count })}</span>
                          <ChevronRight className="log__chevron" aria-hidden />
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </Card>
            </section>
          ))}
      </div>
    </>
  );
}
