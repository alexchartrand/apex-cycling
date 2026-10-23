import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation, useSearchParams } from "react-router-dom";
import { PageHeader, SkeletonGroup } from "../components/ui";
import { ActivityUpload } from "../features/activities/ActivityUpload";
import { IntervalsSource } from "../features/activities/IntervalsSource";
import { StravaSource, type StravaReturn } from "../features/activities/StravaSource";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { SqorzSource } from "../features/connections/SqorzSource";
import { SyncActivity } from "../features/connections/SyncActivity";
import "../features/activities/Activities.css";
import "../features/connections/Connections.css";
import "./ImportPage.css";

const RETURNS: StravaReturn[] = ["connected", "denied", "error"];

export function ImportPage() {
  const { t } = useTranslation(["import", "common"]);
  const athlete = useActiveAthlete();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const { hash } = useLocation();
  const stravaParam = params.get("strava");
  const returned = RETURNS.find((value) => value === stravaParam) ?? null;

  // Back from Strava's consent screen: the connection and its first import changed.
  useEffect(() => {
    if (returned) void queryClient.invalidateQueries({ queryKey: ["strava"] });
  }, [returned, queryClient]);
  useEffect(() => {
    if (!returned) return;
    const timer = setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: ["strava"] });
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    }, 3000);
    return () => clearTimeout(timer);
  }, [returned, queryClient]);

  // /import#sqorz (the Home checklist) lands on the transponder card, which sits below the file sources.
  const ready = athlete.data !== undefined;
  useEffect(() => {
    if (!ready || hash !== "#sqorz") return;
    const scroll = () => document.getElementById("sqorz")?.scrollIntoView({ block: "start" });
    scroll();
    // The cards above load their own data and push this one down; land on it once they have.
    const timer = setTimeout(scroll, 700);
    return () => clearTimeout(timer);
  }, [ready, hash]);

  // The banner is shown once; a refresh shouldn't repeat it.
  useEffect(() => {
    if (!stravaParam) return;
    const timer = setTimeout(() => {
      const next = new URLSearchParams(params);
      next.delete("strava");
      setParams(next, { replace: true });
    }, 15000);
    return () => clearTimeout(timer);
  }, [stravaParam, params, setParams]);

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      {athlete.isLoading && <SkeletonGroup lines={6} />}
      {athlete.isError && <p role="alert">{t("common:loadError")}</p>}
      {athlete.data && (
        <div className="import-page">
          <div className="import-page__main">
            <ActivityUpload athleteId={athlete.data.id} />
            <IntervalsSource athleteId={athlete.data.id} />
            <StravaSource athleteId={athlete.data.id} returned={returned} />
            <SqorzSource athleteId={athlete.data.id} />
          </div>
          <aside className="import-page__side">
            <SyncActivity athleteId={athlete.data.id} />
          </aside>
        </div>
      )}
    </>
  );
}
