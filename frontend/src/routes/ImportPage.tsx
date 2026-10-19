import { Activity, FileUp, Waves } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, PageHeader, SkeletonGroup } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { SqorzSource } from "../features/connections/SqorzSource";
import { SyncActivity } from "../features/connections/SyncActivity";
import "../features/connections/Connections.css";
import "./ImportPage.css";

const UPCOMING = [
  { key: "files", icon: FileUp },
  { key: "strava", icon: Activity },
  { key: "intervals", icon: Waves },
] as const;

export function ImportPage() {
  const { t } = useTranslation(["import", "common"]);
  const athlete = useActiveAthlete();

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      {athlete.isLoading && <SkeletonGroup lines={6} />}
      {athlete.isError && <p role="alert">{t("common:loadError")}</p>}
      {athlete.data && (
        <div className="import-page">
          <div className="import-page__main">
            <SqorzSource athleteId={athlete.data.id} />
            <div className="import-upcoming">
              {UPCOMING.map(({ key, icon: Icon }) => (
                <div key={key} className="import-upcoming__card">
                  <div className="import-upcoming__head">
                    <h4>{t(`sources.${key}.title`)}</h4>
                    <Icon aria-hidden />
                  </div>
                  <p>{t(`sources.${key}.description`)}</p>
                  <Badge tone="accent">{t("comingSoon")}</Badge>
                </div>
              ))}
            </div>
          </div>
          <aside className="import-page__side">
            <SyncActivity athleteId={athlete.data.id} />
          </aside>
        </div>
      )}
    </>
  );
}
