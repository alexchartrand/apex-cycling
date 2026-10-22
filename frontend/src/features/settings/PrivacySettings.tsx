import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Card, Checkbox, useToast } from "../../components/ui";
import type { Athlete } from "../athletes/types";
import { useSetLeaderboardConsent } from "../athletes/useAthlete";
import type { User } from "../auth/types";
import { useMyClubs } from "../clubs/useClubs";

/** What other people may see: for now, whether the athlete's best times show on each of their clubs' leaderboards. */
export function PrivacySettings({ athlete, user }: { athlete: Athlete; user: User }) {
  const { t } = useTranslation("settings");
  const { toast } = useToast();
  const consent = useSetLeaderboardConsent(athlete.id);
  const myClubs = useMyClubs();
  // Consent is the athlete's: a coach looking at this profile can't give it. A managed athlete has no login, so their club's admins decide.
  const canChange = athlete.user_id === user.id || athlete.user_id === null;
  // Named from the viewer's own clubs; a club the viewer isn't in has no name to show.
  const clubs = (myClubs.data ?? []).filter((club) => athlete.club_ids.includes(club.id));
  const inClub = athlete.club_ids.length > 0;

  async function handleChange(clubId: string, next: boolean) {
    try {
      await consent.mutateAsync({ clubId, optIn: next });
      toast({ title: next ? t("privacy.leaderboard.on") : t("privacy.leaderboard.off"), tone: "success" });
    } catch {
      // surfaced below
    }
  }

  return (
    <Card title={t("privacy.title")} as="section">
      <p className="settings-section__description">{t("privacy.description")}</p>
      {clubs.map((club) => (
        <Checkbox
          key={club.id}
          label={t("privacy.leaderboard.label", { club: club.name })}
          checked={athlete.leaderboard_club_ids.includes(club.id)}
          disabled={!canChange || consent.isPending}
          onChange={(e) => void handleChange(club.id, e.target.checked)}
        />
      ))}
      <p className="settings-section__description">{t("privacy.leaderboard.hint")}</p>
      {!inClub && (
        <p className="settings-section__description">
          {t("privacy.leaderboard.noClub")} <Link to="/club">{t("privacy.leaderboard.toClubs")}</Link>
        </p>
      )}
      {inClub && !canChange && <p className="settings-section__description">{t("privacy.leaderboard.notYours")}</p>}
      {consent.isError && (
        <p role="alert" className="settings-form__error">
          {errorMessage(consent.error)}
        </p>
      )}
    </Card>
  );
}
