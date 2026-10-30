import { useState } from "react";
import { ArrowRight, UserMinus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Avatar, Button, ButtonLink, Card, ConfirmDialog, EmptyState, SkeletonGroup, useToast } from "../../components/ui";
import { coachAthletePath } from "../athletes/athleteScope";
import { AthleteBadges, AthleteFacts } from "./AthleteSummary";
import type { AthleteCard, CoachLink } from "./types";
import { useCoachDashboard, useCoachedAthletes, useRevokeCoachLink } from "./useCoaching";

function AthleteCardView({ card, onStop }: { card: AthleteCard; onStop: () => void }) {
  const { t } = useTranslation("coach");
  const last = card.last_session;
  const summary = coachAthletePath(card.athlete_id);

  return (
    <Card as="article" className="coach-card">
      <header className="coach-card__head">
        <Avatar name={card.athlete_name} />
        <h3 className="coach-card__name">
          <Link to={summary}>{card.athlete_name}</Link>
        </h3>
      </header>

      <AthleteBadges card={card} />
      <AthleteFacts card={card} />

      <footer className="coach-card__actions">
        <ButtonLink to={summary} size="sm" iconRight={<ArrowRight aria-hidden />}>
          {t("cards.view")}
        </ButtonLink>
        {last && (
          <ButtonLink to={coachAthletePath(card.athlete_id, `/sessions/${encodeURIComponent(last.external_event_id)}`)} size="sm" variant="secondary">
            {t("cards.openSession")}
          </ButtonLink>
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
