import { useMemo, useState } from "react";
import { Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, EmptyState, PageHeader, SegmentedControl, Select, SkeletonGroup } from "../components/ui";
import { CurveChart } from "../features/activities/CurveChart";
import { durationLabel } from "../features/activities/format";
import { changePercent, compareCurves, headlinePowers, rangeBounds, type RangeKey } from "../features/activities/powerCurve";
import { usePowerCurve } from "../features/activities/useActivities";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { useCurrentMetrics } from "../features/athletes/useAthlete";
import { useFormat } from "../i18n/useFormat";
import "../features/activities/Activities.css";
import "./PowerCurvePage.css";

type CompareMode = "none" | "before" | "allTime";
type Unit = "watts" | "perKg";

const RANGES: RangeKey[] = ["28d", "90d", "365d", "all"];
const RANGE_DAYS: Record<RangeKey, number> = { "28d": 28, "90d": 90, "365d": 365, all: 0 };

export function PowerCurvePage() {
  const { t } = useTranslation(["activities", "shell", "common"]);
  const fmt = useFormat();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const weight = useCurrentMetrics(athleteId).data?.weight_kg?.value ?? null;

  const [range, setRange] = useState<RangeKey>("90d");
  const [compare, setCompare] = useState<CompareMode>("before");
  const [unit, setUnit] = useState<Unit>("watts");

  // Fixed per mount: bounds are instants, and a moving "now" would refetch on every render.
  const [now] = useState(() => new Date());
  const selected = useMemo(() => rangeBounds(range, now), [range, now]);
  const previous = useMemo(
    () => (range === "all" ? null : rangeBounds(range, now, RANGE_DAYS[range])),
    [range, now],
  );
  const comparedBounds = compare === "before" ? previous : compare === "allTime" ? {} : null;

  const main = usePowerCurve(athleteId, selected);
  const other = usePowerCurve(athleteId, comparedBounds ?? {}, comparedBounds !== null);

  const useKg = unit === "perKg" && weight != null;
  const rows = compareCurves(main.data ?? [], comparedBounds ? (other.data ?? []) : [], useKg ? { a: weight, b: weight } : {});
  const headline = headlinePowers(main.data ?? []);
  const comparedHeadline = comparedBounds ? headlinePowers(other.data ?? []) : null;
  const noRides = main.data?.length === 0 && (comparedBounds === null || other.data?.length === 0);
  const digits = useKg ? 2 : 0;

  return (
    <>
      <PageHeader title={t("power.title")} description={t("power.description")} />

      <Card className="power-page__filters">
        <Select label={t("power.range")} value={range} onChange={(e) => setRange(e.target.value as RangeKey)}>
          {RANGES.map((key) => (
            <option key={key} value={key}>
              {t(`power.ranges.${key}`)}
            </option>
          ))}
        </Select>
        <Select label={t("power.compareWith")} value={compare} onChange={(e) => setCompare(e.target.value as CompareMode)}>
          <option value="none">{t("power.compareModes.none")}</option>
          {range !== "all" && <option value="before">{t("power.compareModes.before")}</option>}
          <option value="allTime">{t("power.compareModes.allTime")}</option>
        </Select>
        <div className="power-page__unit">
          <SegmentedControl<Unit>
            aria-label={t("power.watts")}
            value={useKg ? "perKg" : "watts"}
            onChange={setUnit}
            options={[
              { value: "watts", label: t("power.watts") },
              { value: "perKg", label: t("power.perKg") },
            ]}
          />
          {unit === "perKg" && weight == null && <span className="ui-card__hint">{t("power.noWeight")}</span>}
        </div>
      </Card>

      {main.isLoading && <SkeletonGroup lines={6} />}
      {main.isError && <p role="alert">{t("common:loadError")}</p>}
      {noRides && <EmptyState icon={<Zap aria-hidden />} title={t("power.title")} description={t("power.empty")} />}

      {main.data && !noRides && (
        <div className="power-page">
          <Card>
            <CurveChart
              rows={rows}
              unit={useKg ? t("power.unit.perKg") : t("power.unit.watts")}
              perKg={useKg}
              seriesA={t("power.seriesPeriod")}
              seriesB={comparedBounds ? t("power.seriesCompare") : undefined}
              emptyMessage={t("power.empty")}
            />
          </Card>

          <Card title={t("power.headline")}>
            <ul className="power-page__headline">
              {headline.map(({ duration_s, point }, index) => {
                const value = point ? (useKg && weight ? point.power_w / weight : point.power_w) : null;
                const before = comparedHeadline?.[index].point;
                const beforeValue = before ? (useKg && weight ? before.power_w / weight : before.power_w) : null;
                const change = changePercent(beforeValue, value);
                return (
                  <li key={duration_s} className="power-page__effort">
                    <span className="power-page__duration">{durationLabel(duration_s)}</span>
                    <span className="power-page__value">
                      {value == null ? t("power.noEffort") : `${fmt.number(value, digits)} ${useKg ? t("power.unit.perKg") : t("power.unit.watts")}`}
                    </span>
                    {change != null && (
                      <span className={change >= 0 ? "power-page__change power-page__change--up" : "power-page__change power-page__change--down"}>
                        {change >= 0 ? "+" : "−"}
                        {fmt.number(Math.abs(change), 1)}%
                      </span>
                    )}
                    {point && (
                      <Link to={`/activities/${point.activity_id}`} className="power-page__source" title={t("power.open")}>
                        {t("power.bestOn", { date: fmt.date(new Date(point.start_time), "medium") })}
                      </Link>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
        </div>
      )}
    </>
  );
}
