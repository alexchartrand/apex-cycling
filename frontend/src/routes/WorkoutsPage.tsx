import { Dumbbell, Plus, Search, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Button, ButtonLink, EmptyState, Input, PageHeader, SegmentedControl, Select, SkeletonGroup } from "../components/ui";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { useFormat } from "../i18n/useFormat";
import type { WorkoutFilters, WorkoutSource, WorkoutSummary } from "../features/workouts/types";
import { lengthText } from "../features/workouts/profile";
import { useWorkouts } from "../features/workouts/useWorkouts";
import "../features/workouts/Workouts.css";

type SourceFilter = "all" | WorkoutSource;
type TypeFilter = "all" | "track" | "generic";
type LengthFilter = "" | "short" | "medium" | "long";

// Seconds; "medium" is 45–90 min.
const LENGTHS: Record<Exclude<LengthFilter, "">, Pick<WorkoutFilters, "min_duration_s" | "max_duration_s">> = {
  short: { max_duration_s: 45 * 60 },
  medium: { min_duration_s: 45 * 60, max_duration_s: 90 * 60 },
  long: { min_duration_s: 90 * 60 },
};

/** My workouts, my coaches' and the built-in ones; filters live in the URL. */
export function WorkoutsPage() {
  const { t } = useTranslation("workouts");
  const { t: tc } = useTranslation("common");
  const [params, setParams] = useSearchParams();
  const source = (params.get("source") ?? "all") as SourceFilter;
  const type = (params.get("type") ?? "all") as TypeFilter;
  const length = (params.get("length") ?? "") as LengthFilter;
  const tag = params.get("tag") ?? "";
  const query = useDebouncedValue(params.get("q") ?? "", 300);

  const setParam = (key: string, value: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value === "" || value === "all") next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true },
    );

  const filters: WorkoutFilters = {
    q: query.trim() || undefined,
    tag: tag || undefined,
    source: source === "all" ? undefined : source,
    track: type === "all" ? undefined : type === "track",
    ...(length ? LENGTHS[length] : {}),
  };
  const workouts = useWorkouts(filters);
  const filtered = Object.values(filters).some((value) => value !== undefined);

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <ButtonLink to="/workouts/new" icon={<Plus aria-hidden />}>
            {t("new")}
          </ButtonLink>
        }
      />
      <div className="workouts-page">
        <div className="workout-filters">
          <Input
            className="workout-filters__search"
            type="search"
            aria-label={t("filters.search")}
            placeholder={t("filters.search")}
            value={params.get("q") ?? ""}
            onChange={(e) => setParam("q", e.target.value)}
          />
          <SegmentedControl<SourceFilter>
            size="sm"
            aria-label={t("filters.source")}
            value={source}
            onChange={(value) => setParam("source", value)}
            options={(["all", "mine", "coach", "preset"] as const).map((value) => ({ value, label: t(`filters.sources.${value}`) }))}
          />
          <SegmentedControl<TypeFilter>
            size="sm"
            aria-label={t("filters.type")}
            value={type}
            onChange={(value) => setParam("type", value)}
            options={(["all", "track", "generic"] as const).map((value) => ({ value, label: t(`filters.types.${value}`) }))}
          />
          <Select aria-label={t("filters.length")} value={length} onChange={(e) => setParam("length", e.target.value)}>
            <option value="">{t("filters.lengths.any")}</option>
            <option value="short">{t("filters.lengths.short")}</option>
            <option value="medium">{t("filters.lengths.medium")}</option>
            <option value="long">{t("filters.lengths.long")}</option>
          </Select>
          {tag && (
            <Button size="sm" variant="secondary" iconRight={<X aria-hidden />} onClick={() => setParam("tag", "")} aria-label={t("filters.clearTag", { tag })}>
              #{tag}
            </Button>
          )}
        </div>

        {workouts.data ? (
          workouts.data.length === 0 ? (
            <EmptyState
              icon={filtered ? <Search aria-hidden /> : <Dumbbell aria-hidden />}
              title={filtered ? t("emptyFiltered") : t("empty")}
              action={
                filtered ? (
                  <Button variant="secondary" onClick={() => setParams({}, { replace: true })}>
                    {t("filters.clear")}
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <ul className="workout-grid">
              {workouts.data.map((workout) => (
                <li key={workout.id}>
                  <WorkoutCard workout={workout} onTag={(value) => setParam("tag", value)} />
                </li>
              ))}
            </ul>
          )
        ) : workouts.isError ? (
          <EmptyState compact title={tc("loadError")} />
        ) : (
          <SkeletonGroup lines={4} />
        )}
      </div>
    </>
  );
}

function WorkoutCard({ workout, onTag }: { workout: WorkoutSummary; onTag: (tag: string) => void }) {
  const { t } = useTranslation("workouts");
  const fmt = useFormat();
  return (
    <article className="workout-card">
      <div className="workout-card__badges">
        <Badge tone={workout.source === "mine" ? "accent" : workout.source === "coach" ? "positive" : "neutral"}>
          {workout.source === "coach" && workout.owner_name ? t("sourceBy", { name: workout.owner_name }) : t(`sources.${workout.source}`)}
        </Badge>
        {workout.is_track && <Badge tone="highlight">{t("track")}</Badge>}
      </div>
      <h3 className="workout-card__name">
        <Link to={`/workouts/${workout.id}`}>{workout.name}</Link>
      </h3>
      <p className="workout-card__meta">
        {lengthText(workout.duration_s)}
        {workout.tss != null && ` · ${t("tssValue", { value: fmt.number(workout.tss, 0) })}`}
      </p>
      {workout.description && <p className="workout-card__description">{workout.description}</p>}
      {workout.tags.length > 0 && (
        <div className="workout-card__tags">
          {workout.tags.map((tag) => (
            <button key={tag} type="button" className="workout-tag" onClick={() => onTag(tag)}>
              #{tag}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
