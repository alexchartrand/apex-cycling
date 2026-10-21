import { CalendarDays, CalendarPlus, ChevronLeft, ChevronRight, CloudDownload, HeartPulse, Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Button, ButtonLink, Card, EmptyState, IconButton, PageHeader, SegmentedControl, SkeletonGroup } from "../components/ui";
import { localDay, mpsToKmh } from "../features/activities/format";
import { groupItemsByMonth, mergeLog, monthCalendar, type LogItem } from "../features/activities/logItems";
import { useActivities } from "../features/activities/useActivities";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { PlanDetailDialog } from "../features/plan/PlanDetailDialog";
import { PlanDialog } from "../features/plan/PlanDialog";
import { usePlannedSessions } from "../features/plan/usePlan";
import type { PlannedSession } from "../features/plan/types";
import { useSessions } from "../features/training/useTraining";
import { localIsoDate, parseLocalDate } from "../i18n/format";
import { useFormat } from "../i18n/useFormat";
import "./LogPage.css";

type View = "list" | "calendar";

const MONTH_PARAM = /^(\d{4})-(0[1-9]|1[0-2])$/;

function itemKey(item: LogItem): string {
  return item.kind === "session" ? `s-${item.session.external_event_id}` : `a-${item.activity.id}`;
}

function itemHref(item: LogItem): string {
  return item.kind === "session" ? `/sessions/${item.session.external_event_id}` : `/activities/${item.activity.id}`;
}

export function LogPage() {
  const { t } = useTranslation(["training", "activities", "shell", "common", "plan"]);
  const fmt = useFormat();
  const athlete = useActiveAthlete();
  const athleteId = athlete.data?.id ?? "";
  const sessions = useSessions(athleteId);
  const activities = useActivities(athleteId);
  const plans = usePlannedSessions(athleteId);
  const [planOpen, setPlanOpen] = useState<PlannedSession | null>(null);
  const [planning, setPlanning] = useState(false);
  const [params, setParams] = useSearchParams();
  const view: View = params.get("view") === "calendar" ? "calendar" : "list";

  const today = new Date();
  const requested = MONTH_PARAM.exec(params.get("month") ?? "");
  const year = requested ? Number(requested[1]) : today.getFullYear();
  const monthIndex = requested ? Number(requested[2]) - 1 : today.getMonth();

  const items = mergeLog(sessions.data ?? [], activities.data ?? []);
  const loading = athlete.isLoading || sessions.isLoading || activities.isLoading;
  const failed = athlete.isError || sessions.isError;
  const monthFormat = new Intl.DateTimeFormat(fmt.locale, { month: "long", year: "numeric" });

  function update(next: Record<string, string | null>) {
    const copy = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null) copy.delete(key);
      else copy.set(key, value);
    }
    setParams(copy, { replace: true });
  }

  function goToMonth(delta: number) {
    const target = new Date(year, monthIndex + delta, 1);
    update({ month: `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, "0")}` });
  }

  return (
    <>
      <PageHeader
        title={t("log.title")}
        description={t("log.description")}
        actions={
          <>
            <SegmentedControl<View>
              aria-label={t("activities:log.viewLabel")}
              value={view}
              onChange={(next) => update({ view: next === "list" ? null : next })}
              options={[
                { value: "list", label: t("activities:log.views.list") },
                { value: "calendar", label: t("activities:log.views.calendar") },
              ]}
            />
            <Button variant="secondary" icon={<CalendarPlus aria-hidden />} onClick={() => setPlanning(true)} disabled={athleteId === ""}>
              {t("plan:add")}
            </Button>
            <ButtonLink to="/import" variant="secondary" icon={<CloudDownload aria-hidden />}>
              {t("shell:nav.import")}
            </ButtonLink>
          </>
        }
      />
      {planning && <PlanDialog key="new" athleteId={athleteId} date={localIsoDate()} plan={null} onClose={() => setPlanning(false)} />}
      {planOpen && <PlanDetailDialog key={planOpen.id} athleteId={athleteId} plan={plans.data?.find((p) => p.id === planOpen.id) ?? planOpen} onClose={() => setPlanOpen(null)} />}

      {loading && <SkeletonGroup lines={6} />}
      {failed && <p role="alert">{t("log.loadError")}</p>}

      {!loading && items.length === 0 && !failed && (
        <EmptyState
          icon={<CalendarDays aria-hidden />}
          title={t("log.emptyTitle")}
          description={t("log.emptyDescription")}
          action={<ButtonLink to="/import">{t("log.emptyAction")}</ButtonLink>}
        />
      )}

      {items.length > 0 && view === "list" && (
        <div className="log">
          {groupItemsByMonth(items).map((group) => (
            <section key={group.month} className="log__month">
              <h2 className="log__month-title eyebrow">{monthFormat.format(parseLocalDate(`${group.month}-01`))}</h2>
              <Card padding="flush">
                <ul className="log__list">
                  {group.items.map((item) => (
                    <li key={itemKey(item)}>
                      <Link to={itemHref(item)} className="log__row">
                        <LogRow item={item} />
                        <ChevronRight className="log__chevron" aria-hidden />
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ))}
        </div>
      )}

      {!loading && !failed && view === "calendar" && (
        <section className="log-calendar" aria-label={monthFormat.format(new Date(year, monthIndex, 1))}>
          <div className="log-calendar__nav">
            <IconButton aria-label={t("activities:log.previousMonth")} onClick={() => goToMonth(-1)}>
              <ChevronLeft aria-hidden />
            </IconButton>
            <h2 className="log-calendar__title">{monthFormat.format(new Date(year, monthIndex, 1))}</h2>
            <IconButton aria-label={t("activities:log.nextMonth")} onClick={() => goToMonth(1)}>
              <ChevronRight aria-hidden />
            </IconButton>
            <Button variant="ghost" size="sm" onClick={() => update({ month: null })}>
              {t("activities:log.today")}
            </Button>
          </div>
          <Calendar year={year} monthIndex={monthIndex} items={items} plans={plans.data ?? []} onOpenPlan={setPlanOpen} />
        </section>
      )}
    </>
  );
}

function LogRow({ item }: { item: LogItem }) {
  const { t } = useTranslation(["training", "activities"]);
  const fmt = useFormat();

  if (item.kind === "session") {
    const date = parseLocalDate(item.session.event_date);
    const power = item.activities.some((a) => a.has_power);
    const heartRate = item.activities.some((a) => a.has_heart_rate);
    return (
      <>
        <DateBlock date={date} />
        <span className="log__main">
          <span className="log__name">{item.session.event_name}</span>
          <span className="log__tracks">
            {item.session.track_names.map((name) => (
              <Badge key={name}>{name}</Badge>
            ))}
            {power && (
              <Badge tone="accent" icon={<Zap aria-hidden />}>
                {t("activities:log.withPower")}
              </Badge>
            )}
            {!power && heartRate && (
              <Badge tone="accent" icon={<HeartPulse aria-hidden />}>
                {t("activities:log.withHeartRate")}
              </Badge>
            )}
          </span>
        </span>
        <span className="log__laps">{t("log.laps", { count: item.session.lap_count })}</span>
      </>
    );
  }

  const { activity } = item;
  const date = new Date(activity.start_time);
  const speed = mpsToKmh(activity.avg_speed_mps);
  return (
    <>
      <DateBlock date={date} />
      <span className="log__main">
        <span className="log__name">{activity.name ?? t("activities:untitled", { date: fmt.date(date, "medium") })}</span>
        <span className="log__tracks">
          <Badge>{t("activities:log.ride")}</Badge>
          <Badge>{t(`activities:sources.${activity.source}`)}</Badge>
          {activity.has_power && (
            <Badge tone="accent" icon={<Zap aria-hidden />}>
              {fmt.number(activity.avg_power_w, 0)} W
            </Badge>
          )}
        </span>
      </span>
      <span className="log__laps">
        {fmt.duration(activity.elapsed_s)}
        {activity.distance_m ? ` · ${t("activities:log.km", { distance: fmt.number(activity.distance_m / 1000, 1) })}` : ""}
        {speed ? ` · ${fmt.number(speed, 1)} km/h` : ""}
      </span>
    </>
  );
}

function DateBlock({ date }: { date: Date }) {
  const fmt = useFormat();
  return (
    <span className="log__date">
      <span className="log__day">{date.getDate()}</span>
      <span className="log__weekday">{new Intl.DateTimeFormat(fmt.locale, { weekday: "short" }).format(date)}</span>
    </span>
  );
}

function Calendar({ year, monthIndex, items, plans, onOpenPlan }: { year: number; monthIndex: number; items: LogItem[]; plans: PlannedSession[]; onOpenPlan: (plan: PlannedSession) => void }) {
  const { t } = useTranslation(["activities", "plan"]);
  const fmt = useFormat();
  const weeks = monthCalendar(year, monthIndex, items);
  const todayKey = localDay(new Date().toISOString());
  // Monday-first weekday names from any Monday.
  const weekdays = Array.from({ length: 7 }, (_, i) =>
    new Intl.DateTimeFormat(fmt.locale, { weekday: "short" }).format(new Date(2024, 0, 1 + i)),
  );
  const plansByDay = new Map<string, PlannedSession[]>();
  for (const plan of plans) plansByDay.set(plan.planned_date, [...(plansByDay.get(plan.planned_date) ?? []), plan]);
  const inMonth = weeks.flat().some((day) => day.inMonth && (day.items.length > 0 || plansByDay.has(day.day)));

  return (
    <Card padding="flush">
      <div className="log-calendar__grid" role="grid">
        {weekdays.map((name) => (
          <div key={name} className="log-calendar__weekday" role="columnheader">
            {name}
          </div>
        ))}
        {weeks.flat().map((day) => (
          <div
            key={day.day}
            role="gridcell"
            className={[
              "log-calendar__day",
              !day.inMonth && "log-calendar__day--outside",
              day.day === todayKey && "log-calendar__day--today",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span className="log-calendar__number">{Number(day.day.slice(8))}</span>
            <ul className="log-calendar__items">
              {day.items.map((item) => (
                <li key={itemKey(item)}>
                  <Link
                    to={itemHref(item)}
                    className={`log-calendar__chip log-calendar__chip--${item.kind}`}
                    title={item.kind === "session" ? item.session.event_name : (item.activity.name ?? t("activities:log.ride"))}
                  >
                    <span className="log-calendar__chip-text">
                      {item.kind === "session" ? item.session.event_name : (item.activity.name ?? t("activities:log.ride"))}
                    </span>
                  </Link>
                </li>
              ))}
              {(plansByDay.get(day.day) ?? []).map((plan) => (
                <li key={plan.id}>
                  <button
                    type="button"
                    className={`log-calendar__chip log-calendar__chip--plan log-calendar__chip--plan-${plan.status}`}
                    title={t("plan:chip", { title: plan.title })}
                    onClick={() => onOpenPlan(plan)}
                  >
                    <span className="log-calendar__chip-text">{plan.title}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {!inMonth && <p className="log-calendar__empty ui-card__hint">{t("activities:log.nothingThisMonth")}</p>}
    </Card>
  );
}
