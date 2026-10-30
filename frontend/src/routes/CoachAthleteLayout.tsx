import { useMemo } from "react";
import { ArrowLeft, UserX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { Avatar, ButtonLink, EmptyState, TabPanel, Tabs, type TabItem } from "../components/ui";
import { AthleteScopeContext, coachAthletePath } from "../features/athletes/athleteScope";
import { useCoachAthleteSummary } from "../features/coaching/useCoaching";
import "../features/coaching/Coaching.css";

const SECTIONS = ["summary", "log", "records", "progress", "power", "season"] as const;
type Section = (typeof SECTIONS)[number];

/** Which tab a page under the athlete belongs to: a session or a recording is part of the log. */
function sectionOf(rest: string): Section {
  const first = rest.split("/").filter(Boolean)[0] ?? "";
  if (first === "") return "summary";
  if (first === "sessions" || first === "activities" || first === "compare") return "log";
  return (SECTIONS as readonly string[]).includes(first) ? (first as Section) : "summary";
}

/**
 * A coach's view of one athlete, `/coach/athletes/:athleteId/*`: the athlete
 * pages render inside an `AthleteScopeContext`, so they read this athlete,
 * link within here and hide every edit but comments and plans.
 */
export function CoachAthleteLayout() {
  const { t } = useTranslation("coach");
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { athleteId = "" } = useParams();
  const basePath = coachAthletePath(athleteId);
  const scope = useMemo(() => ({ athleteId, basePath }), [athleteId, basePath]);
  const summary = useCoachAthleteSummary(athleteId);

  if (summary.error instanceof ApiError && summary.error.status === 404) {
    return (
      <EmptyState
        icon={<UserX aria-hidden />}
        title={t("athlete.notFound")}
        description={t("athlete.notFoundHint")}
        action={<ButtonLink to="/coach">{t("athlete.back")}</ButtonLink>}
      />
    );
  }

  const section = sectionOf(pathname.slice(basePath.length));
  const items: TabItem<Section>[] = SECTIONS.map((value) => ({ value, label: t(`athlete.nav.${value}`) }));
  const name = summary.data?.athlete_name ?? "";

  return (
    <AthleteScopeContext.Provider value={scope}>
      <div className="coach-athlete__bar">
        <Link to="/coach" className="coach-athlete__back">
          <ArrowLeft aria-hidden /> {t("athlete.back")}
        </Link>
        {name && (
          <span className="coach-athlete__who">
            <Avatar name={name} size="sm" />
            {name}
          </span>
        )}
      </div>
      <Tabs
        items={items}
        value={section}
        onValueChange={(next) => navigate(next === "summary" ? basePath : `${basePath}/${next}`)}
        aria-label={t("athlete.nav.label", { name })}
      >
        <TabPanel value={section}>
          <Outlet />
        </TabPanel>
      </Tabs>
    </AthleteScopeContext.Provider>
  );
}
