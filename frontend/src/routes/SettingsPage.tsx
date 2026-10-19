import { useTranslation } from "react-i18next";
import { LanguageSwitcher, ThemeSwitcher } from "../components/preferences/PreferenceSwitchers";
import { Card, PageHeader } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { useCurrentUser } from "../features/auth/useAuth";
import "./SettingsPage.css";

/** Interim settings screen; the full profile/physiology/security pages land in T2.3. */
export function SettingsPage() {
  const { t } = useTranslation("settings");
  const { data: user } = useCurrentUser();
  const athlete = useActiveAthlete();

  return (
    <>
      <PageHeader title={t("title")} />
      <div className="settings">
        <Card title={t("profile.title")}>
          <dl className="settings__list">
            <div>
              <dt>{t("profile.name")}</dt>
              <dd>{athlete.data?.display_name}</dd>
            </div>
            <div>
              <dt>{t("profile.email")}</dt>
              <dd>{user?.email}</dd>
            </div>
          </dl>
        </Card>
        <Card title={t("preferences.title")}>
          <div className="settings__pref">
            <span>{t("preferences.language")}</span>
            <LanguageSwitcher size="md" />
          </div>
          <div className="settings__pref">
            <span>{t("preferences.theme")}</span>
            <ThemeSwitcher size="md" showLabels />
          </div>
        </Card>
        <p className="ui-card__hint">{t("more")}</p>
      </div>
    </>
  );
}
