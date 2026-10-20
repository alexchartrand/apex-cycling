import { useState } from "react";
import { AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Eye, MessageSquare, Trophy, UserMinus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Avatar, Badge, Button, Card, ConfirmDialog, EmptyState, SkeletonGroup, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { useViewAthlete } from "../athletes/useViewAthlete";
import { loadChange, signed } from "./loadChange";
import type { AthleteCard, CoachLink } from "./types";
import { useCoachDashboard, useCoachedAthletes, useRevokeCoachLink } from "./useCoaching";

function Trend({ direction }: { direction: ReturnType<typeof loadChange>["direction"] }) {
  if (direction === "up") return <ArrowUpRight aria-hidden className="coach-trend coach-trend--up" />;
  if (direction === "down") return <ArrowDownRight aria-hidden className="coach-trend coach-trend--down" />;
  return <ArrowRight aria-hidden className="coach-trend" />;
}

function AthleteCardView({ card, onStop }: { card: AthleteCard; onStop: () => void }) {
  const { t } = useTranslation("coach");
  const fmt = useFormat();
  const view = useViewAthlete();
  const change = loadChange(card.this_week, card.previous_week);
  const last = card.last_session;

  return (
    <Card as="article" className="coach-card">
      <header className="coach-card__head">
        <Avatar name={card.athlete_name} />
        <h3 className="coach-card__name">{card.athlete_name}</h3>
      </header>

      <div className="coach-card__badges">
        {card.failing_transponders.length > 0 && (
          <Badge tone="negative" icon={<AlertTriangle aria-hidden />}>
            {t("cards.syncFailing", { codes: card.failing_transponders.join(", ") })}
          </Badge>
        )}
        {card.new_records > 0 && (
          <Badge tone="highlight" icon={<Trophy aria-hidden />}>
            {t("cards.newRecords", { count: card.new_records })}
          </Badge>
        )}
        {card.unread_comments > 0 && (
          <Badge tone="accent" icon={<MessageSquare aria-hidden />}>
            {t("cards.unread", { count: card.unread_comments })}
          </Badge>
        )}
      </div>

      <dl className="coach-card__facts">
        <div>
          <dt>{t("cards.lastSession")}</dt>
          <dd>
            {last ? (
              <>
                {last.name}
                <span className="coach-card__sub">
                  {fmt.date(last.event_date, "weekday")} · {t("cards.laps", { count: last.lap_count })}
                </span>
              </>
            ) : (
              <span className="coach-card__sub">{t("cards.noSessions")}</span>
            )}
          </dd>
        </div>
        <div>
          <dt>{t("cards.thisWeek")}</dt>
          <dd>
            {t("cards.sessions", { count: card.this_week.sessions })} · {t("cards.laps", { count: card.this_week.laps })}
            {change.direction !== "none" && (
              <span className="coach-card__sub">
                <Trend direction={change.direction} /> {t("cards.vsLastWeek", { laps: signed(change.laps) })}
              </span>
            )}
          </dd>
        </div>
        {card.this_week.avg_rpe !== null && (
          <div>
            <dt>{t("cards.effort")}</dt>
            <dd>{t("cards.rpe", { value: fmt.number(card.this_week.avg_rpe, 1) })}</dd>
          </div>
        )}
      </dl>

      <footer className="coach-card__actions">
        <Button size="sm" icon={<Eye aria-hidden />} onClick={() => view(card.athlete_id)}>
          {t("cards.view")}
        </Button>
        {last && (
          <Button size="sm" variant="secondary" onClick={() => view(card.athlete_id, `/sessions/${last.external_event_id}`)}>
            {t("cards.openSession")}
          </Button>
        )}
        <Button size="sm" variant="ghost" icon={<UserMinus aria-hidden />} onClick={onStop}>
          {t("cards.stop")}
        </Button>
      </footer>
    </Card>
  );
}

/** One summary card per athlete the user actively coaches, plus the requests still waiting on the athlete. */
export function AthleteCards() {
  const { t } = useTranslation("coach");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const dashboard = useCoachDashboard();
  const links = useCoachedAthletes();
  const revoke = useRevokeCoachLink();
  const [stopping, setStopping] = useState<AthleteCard | null>(null);

  const linkFor = (athleteId: string) => links.data?.find((link) => link.athlete_id === athleteId && link.status === "active");
  const waiting: CoachLink[] = (links.data ?? []).filter((link) => link.status === "pending_athlete_acceptance");

  return (
    <div className="coach-stack">
      {dashboard.isLoading && <SkeletonGroup lines={5} />}
      {dashboard.isError && <p role="alert">{tc("loadError")}</p>}
      {dashboard.data && dashboard.data.length === 0 && (
        <EmptyState compact title={t("cards.emptyTitle")} description={t("cards.emptyDescription")} />
      )}
      {dashboard.data && dashboard.data.length > 0 && (
        <div className="coach-grid">
          {dashboard.data.map((card) => (
            <AthleteCardView key={card.athlete_id} card={card} onStop={() => setStopping(card)} />
          ))}
        </div>
      )}

      {waiting.length > 0 && (
        <Card as="section" title={t("cards.sentTitle")}>
          <ul className="coach-waiting">
            {waiting.map((link) => (
              <li key={link.id} className="coach-waiting__row">
                <span className="coach-waiting__text">{t("cards.sentTo", { athlete: link.athlete_name })}</span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    try {
                      await revoke.mutateAsync(link.id);
                    } catch (error) {
                      toast({ title: errorMessage(error), tone: "error" });
                    }
                  }}
                >
                  {t("cards.cancel")}
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <ConfirmDialog
        open={stopping !== null}
        onOpenChange={(open) => !open && setStopping(null)}
        tone="danger"
        title={t("cards.stopTitle", { name: stopping?.athlete_name ?? "" })}
        description={t("cards.stopDescription")}
        confirmLabel={t("cards.stopConfirm")}
        cancelLabel={tc("cancel")}
        onConfirm={async () => {
          const link = stopping && linkFor(stopping.athlete_id);
          if (!link) return;
          try {
            await revoke.mutateAsync(link.id);
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
          toast({ title: t("cards.stopped"), tone: "success" });
        }}
      />
    </div>
  );
}
