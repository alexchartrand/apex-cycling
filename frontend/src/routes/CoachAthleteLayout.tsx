import { useMemo } from "react";
import { ArrowLeft, UserX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { Avatar, ButtonLink, EmptyState, TabPanel, Tabs, type TabItem } from "../components/ui";
import { SubNav } from "../components/shell/SubNav";
import { AthleteScopeContext, coachAthletePath } from "../features/athletes/athleteScope";
import { useCoachAthleteSummary } from "../features/coaching/useCoaching";
import { useAiAccess } from "../features/aicoach/useAiCoach";
import { useAthlete } from "../features/athletes/useAthlete";
import { pageShown } from "../features/sports/registry";
import { useAthleteSports } from "../features/sports/useMySports";
import "../features/coaching/Coaching.css";

type Page = "summary" | "log" | "records" | "progress" | "power" | "season" | "plans" | "ai";
const PAGES: readonly Page[] = ["summary", "log", "records", "progress", "power", "season", "plans", "ai"];

/** The coach view's tabs, grouped like the app's hubs. */
const SECTIONS = {
  summary: ["summary"],
  log: ["log"],
  train: ["plans", "season", "ai"],
  progress: ["progress", "records", "power"],
} as const satisfies Record<string, readonly Page[]>;
type Section = keyof typeof SECTIONS;

/** Which page a path under the athlete is: a session or a recording is part of the log. */
function pageOf(rest: string): Page {
  const first = rest.split("/").filter(Boolean)[0] ?? "";
  if (first === "") return "summary";
  if (first === "sessions" || first === "activities" || first === "compare") return "log";
  return (PAGES as readonly string[]).includes(first) ? (first as Page) : "summary";
}

function sectionOf(page: Page): Section {
  return (Object.keys(SECTIONS) as Section[]).find((key) => (SECTIONS[key] as readonly Page[]).includes(page)) ?? "summary";
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
  const aiCoach = useAiAccess(athleteId || undefined).data?.enabled ?? false;
  const { sports } = useAthleteSports(useAthlete(athleteId).data);

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

  const page = pageOf(pathname.slice(basePath.length));
  const section = sectionOf(page);
  // The AI coach page only for an athlete who has one.
  const pagesOf = (key: Section): Page[] =>
    SECTIONS[key].filter((value) => (value !== "ai" || aiCoach) && pageShown(value, sports));
  const pathOf = (value: Page) => (value === "summary" ? basePath : `${basePath}/${value}`);
  const items: TabItem<Section>[] = (Object.keys(SECTIONS) as Section[]).map((value) => ({
    value,
    label: t(`athlete.nav.${value}`),
  }));
  const subPages = pagesOf(section);
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
        onValueChange={(next) => navigate(pathOf(pagesOf(next)[0]))}
        aria-label={t("athlete.nav.label", { name })}
      >
        <TabPanel value={section}>
          {subPages.length > 1 && (
            <SubNav
              aria-label={t(`athlete.nav.${section}`)}
              items={subPages.map((value) => ({
                key: value,
                to: pathOf(value),
                label: t(`athlete.pages.${value}`),
                active: value === page,
              }))}
            />
          )}
          <Outlet />
        </TabPanel>
      </Tabs>
    </AthleteScopeContext.Provider>
  );
}
