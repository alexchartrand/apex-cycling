import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps, secondsDomain } from "../../components/charts";
import { Badge, Card, EmptyState, SkeletonGroup } from "../../components/ui";
import { parseLocalDate } from "../../i18n/format";
import { useFormat } from "../../i18n/useFormat";
import { improvements } from "./recordsBoard";
import { formatRecordTime } from "./timeInput";
import type { RecordSelection, StandardEventKey } from "./types";
import { useRecordHistory } from "./useRecords";
import { Trophy } from "lucide-react";
import "./RecordTimeline.css";

/** The chain of results that each set a new record, as a step line plus a list with the gain of each. */
export function RecordTimeline({ athleteId, selection }: { athleteId: string; selection: RecordSelection | null }) {
  const { t } = useTranslation("records");
  const fmt = useFormat();
  const history = useRecordHistory(athleteId, selection);

  if (!selection) {
    return (
      <Card as="section">
        <EmptyState compact icon={<Trophy aria-hidden />} title={t("timeline.pick")} />
      </Card>
    );
  }

  const entries = history.data ?? [];
  const gains = improvements(entries);
  const data = entries.map((entry) => ({ t: parseLocalDate(entry.achieved_on).getTime(), ms: entry.time_ms }));

  return (
    <Card
      as="section"
      title={t("timeline.title", {
        event: t(`events.${selection.event_key as StandardEventKey}`),
        start: t(`startTypes.${selection.start_type}`),
      })}
      eyebrow={t("timeline.subtitle", { place: selection.place })}
    >
      {history.isLoading && <SkeletonGroup lines={5} />}
      {history.isError && <p role="alert">{t("timeline.loadError")}</p>}
      {history.data && (
        <>
          <ChartFrame
            height={240}
            isEmpty={entries.length === 0}
            emptyMessage={t("timeline.empty")}
            legend={[{ label: t("timeline.seriesLabel"), color: "var(--chart-1)" }]}
            caption={t("timeline.chartCaption")}
          >
            <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid {...gridProps} />
              <XAxis
                dataKey="t"
                type="number"
                scale="time"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(value: number) => fmt.date(new Date(value), "dayMonth")}
                minTickGap={32}
                padding={{ left: 12, right: 12 }}
                {...axisProps}
              />
              <YAxis domain={secondsDomain} tickFormatter={(ms: number) => formatRecordTime(ms, fmt)} width={72} {...axisProps} />
              <Tooltip
                cursor={cursorProps}
                content={<ChartTooltip formatValue={(ms) => formatRecordTime(ms, fmt)} formatLabel={(value) => fmt.date(new Date(Number(value)), "medium")} />}
              />
              <Line
                type="stepAfter"
                dataKey="ms"
                name={t("timeline.seriesLabel")}
                stroke="var(--chart-1)"
                strokeWidth={2}
                dot={{ r: 4, fill: "var(--chart-1)", strokeWidth: 0 }}
                activeDot={{ r: 6 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ChartFrame>

          {entries.length > 0 && (
            <table className="record-timeline__table">
              <thead>
                <tr>
                  <th scope="col">{t("timeline.date")}</th>
                  <th scope="col">{t("timeline.time")}</th>
                  <th scope="col">{t("timeline.change")}</th>
                  <th scope="col">{t("board.source")}</th>
                </tr>
              </thead>
              <tbody>
                {[...entries.keys()].reverse().map((i) => {
                  const entry = entries[i];
                  const gain = gains[i];
                  return (
                    <tr key={`${entry.achieved_on}-${entry.time_ms}-${i}`}>
                      <td>{fmt.date(entry.achieved_on, "medium")}</td>
                      <td className="record-timeline__time">{formatRecordTime(entry.time_ms, fmt)}</td>
                      <td>{gain == null ? <span className="record-timeline__muted">{t("timeline.first")}</span> : <Badge tone="positive">{fmt.deltaSeconds(gain)} s</Badge>}</td>
                      <td>
                        {entry.source === "sqorz" && entry.external_event_id ? (
                          <Link className="records-board__link" to={`/sessions/${entry.external_event_id}`}>
                            {t("board.session")}
                          </Link>
                        ) : (
                          <Badge>{t("board.manual")}</Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </>
      )}
    </Card>
  );
}
