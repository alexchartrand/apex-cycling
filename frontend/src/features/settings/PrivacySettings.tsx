import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Card, Checkbox, useToast } from "../../components/ui";
import type { Athlete } from "../athletes/types";
import { useUpdateAthlete } from "../athletes/useAthlete";
import type { User } from "../auth/types";

/** What other people may see: for now, whether the athlete's best times show on their club's leaderboard. */
export function PrivacySettings({ athlete, user }: { athlete: Athlete; user: User }) {
  const { t } = useTranslation("settings");
  const { toast } = useToast();
  const update = useUpdateAthlete(athlete.id);
  // Consent is the athlete's: a coach looking at this profile can't give it. A managed athlete has no login, so their club's admins decide.
  const canChange = athlete.user_id === user.id || athlete.user_id === null;
  const inClub = athlete.club_id !== null;

  async function handleChange(next: boolean) {
    try {
      await update.mutateAsync({ leaderboard_opt_in: next });
      toast({ title: next ? t("privacy.leaderboard.on") : t("privacy.leaderboard.off"), tone: "success" });
    } catch {
      // surfaced below
    }
  }

  return (
    <Card title={t("privacy.title")} as="section">
      <p className="settings-section__description">{t("privacy.description")}</p>
      <Checkbox
        label={t("privacy.leaderboard.label")}
        checked={athlete.leaderboard_opt_in}
        disabled={!canChange || !inClub || update.isPending}
        onChange={(e) => void handleChange(e.target.checked)}
      />
      <p className="settings-section__description">{t("privacy.leaderboard.hint")}</p>
      {!inClub && (
        <p className="settings-section__description">
          {t("privacy.leaderboard.noClub")} <Link to="/club">{t("privacy.leaderboard.toClubs")}</Link>
        </p>
      )}
      {inClub && !canChange && <p className="settings-section__description">{t("privacy.leaderboard.notYours")}</p>}
      {update.isError && (
        <p role="alert" className="settings-form__error">
          {errorMessage(update.error)}
        </p>
      )}
    </Card>
  );
}
