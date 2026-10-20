import { useState } from "react";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps } from "../../components/charts";
import { Badge, Card, SegmentedControl, SkeletonGroup, StatTile } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { FORM_TONE, loadChartRows, summarizeLoad } from "./fitness";
import { useTrainingLoad } from "./useActivities";

const RANGES = [42, 90, 180] as const;
type Range = (typeof RANGES)[number];

/**
 * Fitness (CTL), fatigue (ATL) and form (TSB) over time. On the home page it hides
 * itself until there is load to show; on the progress page it explains why not.
 */
export function FitnessCard({ athleteId, hideWhenEmpty = false }: { athleteId: string; hideWhenEmpty?: boolean }) {
  const { t } = useTranslation(["activities", "common"]);
  const fmt = useFormat();
  const [days, setDays] = useState<Range>(90);
  const load = useTrainingLoad(athleteId, days);

  const rows = loadChartRows(load.data?.days ?? []);
  const summary = summarizeLoad(load.data?.days ?? []);
  const unrated = load.data?.unrated_activities ?? 0;
  if (hideWhenEmpty && !load.isLoading && !summary && unrated === 0) return null;

  const formatDay = (value: number) => fmt.date(new Date(value), "dayMonth");
  const change = summary ? `${summary.ctlWeekChange >= 0 ? "+" : "−"}${fmt.number(Math.abs(summary.ctlWeekChange), 1)}` : "";

  return (
    <Card
      title={t("fitness.title")}
      actions={
        <SegmentedControl<`${Range}`>
          size="sm"
          aria-label={t("fitness.title")}
          value={`${days}`}
          onChange={(next) => setDays(Number(next) as Range)}
          options={RANGES.map((range) => ({ value: `${range}` as `${Range}`, label: t(`fitness.range.d${range}`) }))}
        />
      }
    >
      <p className="ui-card__hint">{t("fitness.description")}</p>
      {load.isLoading && <SkeletonGroup lines={4} />}
      {load.isError && <p role="alert">{t("common:loadError")}</p>}

      {!load.isLoading && !summary && <p className="ui-card__hint">{t("fitness.empty")}</p>}

      {summary && (
        <>
          <div className="fitness__tiles">
            <StatTile
              label={t("fitness.fitness")}
              value={fmt.number(summary.ctl, 0)}
              delta={{ label: t("fitness.weekChange", { change }), direction: summary.ctlWeekChange > 0.5 ? "better" : summary.ctlWeekChange < -0.5 ? "worse" : "neutral" }}
            />
            <StatTile label={t("fitness.fatigue")} value={fmt.number(summary.atl, 0)} />
            <StatTile
              label={t("fitness.form")}
              value={`${summary.tsb > 0 ? "+" : summary.tsb < 0 ? "−" : ""}${fmt.number(Math.abs(summary.tsb), 0)}`}
              hint={<Badge tone={FORM_TONE[summary.state]}>{t(`fitness.states.${summary.state}`)}</Badge>}
            />
          </div>

          <ChartFrame
            height={200}
            legend={[
              { label: t("fitness.fitness"), color: "var(--chart-1)" },
              { label: t("fitness.fatigue"), color: "var(--chart-4)" },
            ]}
          >
            <LineChart data={rows} syncId="fitness" margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid {...gridProps} />
              <XAxis {...axisProps} dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={formatDay} hide />
              <YAxis {...axisProps} width={36} tickFormatter={(v: number) => fmt.number(v, 0)} />
              <Tooltip
                cursor={cursorProps}
                content={<ChartTooltip formatLabel={(label) => formatDay(Number(label))} formatValue={(value) => fmt.number(value, 0)} />}
              />
              <Line type="monotone" dataKey="ctl" name={t("fitness.fitness")} stroke="var(--chart-1)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="atl" name={t("fitness.fatigue")} stroke="var(--chart-4)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            </LineChart>
          </ChartFrame>
          <ChartFrame height={96}>
            <AreaChart data={rows} syncId="fitness" margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid {...gridProps} />
              <XAxis {...axisProps} dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={formatDay} />
              <YAxis {...axisProps} width={36} tickFormatter={(v: number) => fmt.number(v, 0)} />
              <ReferenceLine y={0} stroke="var(--color-border-strong)" />
              <Tooltip
                cursor={cursorProps}
                content={<ChartTooltip formatLabel={(label) => formatDay(Number(label))} formatValue={(value) => fmt.number(value, 0)} />}
              />
              <Area type="monotone" dataKey="tsb" name={t("fitness.form")} stroke="var(--chart-3)" fill="var(--chart-3)" fillOpacity={0.2} strokeWidth={1.5} dot={false} isAnimationActive={false} />
            </AreaChart>
          </ChartFrame>
        </>
      )}

      {unrated > 0 && <p className="source-card__note">{t("fitness.unrated", { count: unrated })}</p>}
      <p className="source-card__note">
        <Link to="/power">{t("fitness.powerCurveLink")}</Link>
        {" · "}
        <Link to="/settings/physiology">{t("fitness.managePhysiology")}</Link>
      </p>
    </Card>
  );
}
