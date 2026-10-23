import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { LanguageSwitcher, ThemeSwitcher } from "../components/preferences/PreferenceSwitchers";
import { Card, EmptyState, PageHeader, Skeleton, TabPanel, Tabs, type TabItem } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { useCurrentUser } from "../features/auth/useAuth";
import { NotificationSettings } from "../features/notifications/NotificationSettings";
import { AccountSettings } from "../features/settings/AccountSettings";
import { PrivacySettings } from "../features/settings/PrivacySettings";
import { PhysiologySettings } from "../features/settings/PhysiologySettings";
import { ProfileSettings } from "../features/settings/ProfileSettings";
import "./SettingsPage.css";

const SECTIONS = ["profile", "physiology", "privacy", "notifications", "preferences", "account"] as const;
type Section = (typeof SECTIONS)[number];

function isSection(value: string | undefined): value is Section {
  return SECTIONS.includes(value as Section);
}

export function SettingsPage() {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const navigate = useNavigate();
  const section = useParams()["*"];
  const { data: user } = useCurrentUser();
  const athlete = useActiveAthlete();

  if (!isSection(section)) return <Navigate to="/settings/profile" replace />;

  const items: TabItem<Section>[] = SECTIONS.map((value) => ({ value, label: t(`sections.${value}`) }));

  return (
    <>
      <PageHeader title={t("title")} />
      <div className="settings">
        <Tabs items={items} value={section} onValueChange={(next) => navigate(`/settings/${next}`)} aria-label={t("title")}>
          {(section === "profile" || section === "physiology" || section === "privacy") && !athlete.data ? (
            <TabPanel value={section}>
              {athlete.isError ? <EmptyState compact title={tc("loadError")} /> : <Skeleton height="12rem" />}
            </TabPanel>
          ) : (
            <>
              <TabPanel value="profile">
                {athlete.data && user && <ProfileSettings athlete={athlete.data} user={user} />}
              </TabPanel>
              <TabPanel value="physiology">
                {athlete.data && <PhysiologySettings athleteId={athlete.data.id} />}
              </TabPanel>
              <TabPanel value="privacy">
                {athlete.data && user && <PrivacySettings athlete={athlete.data} user={user} />}
              </TabPanel>
              <TabPanel value="notifications">
                <NotificationSettings />
              </TabPanel>
              <TabPanel value="preferences">
                <Card title={t("preferences.title")} as="section">
                  <p className="settings-section__description">{t("preferences.description")}</p>
                  <div className="settings__pref">
                    <span>{t("preferences.language")}</span>
                    <LanguageSwitcher size="md" />
                  </div>
                  <div className="settings__pref">
                    <span>{t("preferences.theme")}</span>
                    <ThemeSwitcher size="md" showLabels />
                  </div>
                </Card>
              </TabPanel>
              <TabPanel value="account">
                <AccountSettings />
              </TabPanel>
            </>
          )}
        </Tabs>
      </div>
    </>
  );
}
