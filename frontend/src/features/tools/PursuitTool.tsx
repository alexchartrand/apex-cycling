import { useState } from "react";
import { MonitorPlay } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ButtonLink, Card, DataTable, Input, Select, StatTile, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { useActiveAthlete } from "../athletes/useActiveAthlete";
import { useSessionEfforts, useSessions } from "../training/useTraining";
import { effortElapsedByLap, type ScheduleRow } from "./pursuitSchedule";
import { ConditionsCard, NumberField, RiderCard } from "./ToolFields";
import { TIME_PARAM } from "./toolInputs";
import { PURSUIT_KEYS, usePursuitSchedule } from "./usePursuitSchedule";
import type { ToolInputs } from "./useToolInputs";

/** Only multi-lap efforts are worth comparing with a schedule. */
const MIN_COMPARE_LAPS = 2;

export function PursuitTool({ inputs }: { inputs: ToolInputs }) {
  const { t } = useTranslation("tools");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const result = usePursuitSchedule(inputs);
  const [elapsedByLap, setElapsedByLap] = useState<number[] | null>(null);
  const riderKg = inputs.field("riderKg").value;

  const columns: DataTableColumn<ScheduleRow>[] = [
    {
      id: "lap",
      header: t("pursuit.lap"),
      cell: (row) => (row.lap !== null ? <strong>{row.lap}</strong> : <span className="tools-half">½</span>),
    },
    { id: "distance", header: t("pursuit.distance"), align: "right", cell: (row) => `${fmt.number(row.distanceM, 0)} m` },
    { id: "elapsed", header: t("pursuit.elapsed"), align: "right", cell: (row) => fmt.lapTime(row.elapsedS * 1000) },
    {
      id: "lapTime",
      header: t("pursuit.lapTime"),
      align: "right",
      cell: (row) => (row.lapS === null ? "" : fmt.seconds(row.lapS * 1000, 2)),
    },
    { id: "split", header: t("pursuit.split"), align: "right", cell: (row) => fmt.seconds(row.splitS * 1000, 2) },
  ];
  if (elapsedByLap) {
    const actualAt = (row: ScheduleRow) => (row.lap === null ? undefined : elapsedByLap[row.lap - 1]);
    columns.push(
      {
        id: "actual",
        header: t("pursuit.actual"),
        align: "right",
        cell: (row) => {
          const actual = actualAt(row);
          return actual === undefined ? "" : fmt.lapTime(actual * 1000);
        },
      },
      {
        id: "delta",
        header: t("pursuit.delta"),
        align: "right",
        cell: (row) => {
          const actual = actualAt(row);
          if (actual === undefined) return "";
          const delta = actual - row.elapsedS;
          return (
            <span className={delta <= 0 ? "tools-delta tools-delta--ahead" : "tools-delta tools-delta--behind"}>
              {fmt.deltaSeconds(delta * 1000, 2)}
            </span>
          );
        },
      },
    );
  }

  return (
    <div className="tools-tool">
      <Card title={t("effort.title")} as="section">
        <div className="tools-grid">
          <NumberField inputs={inputs} name="distanceM" label={t("effort.distance")} suffix="m" />
          <Input
            label={t("effort.time")}
            hint={t("effort.timeHint")}
            error={inputs.time.invalid ? t("errors.time") : undefined}
            inputMode="decimal"
            autoComplete="off"
            value={inputs.time.raw}
            onChange={(event) => inputs.setParam(TIME_PARAM, event.target.value)}
          />
          <NumberField inputs={inputs} name="lapM" label={t("effort.lap")} suffix="m" />
        </div>
      </Card>

      {result.kind === "invalid" && <p className="tools-note">{t("results.invalid")}</p>}
      {result.kind === "unreachable" && (
        <p className="tools-note" role="status">
          {t("results.unreachable")}
        </p>
      )}
      {result.kind === "ok" && (
        <>
          <div className="tools-results">
            <StatTile
              label={t("pursuit.needs")}
              value={fmt.number(result.schedule.powerW, 0)}
              unit={tc("units.w")}
              tone="accent"
              size="lg"
              hint={riderKg ? `${fmt.number(result.schedule.powerW / riderKg, 2, 2)} ${tc("units.wkg")}` : undefined}
            />
            <StatTile
              label={t("results.averagePower")}
              value={fmt.number(result.schedule.averagePowerW, 0)}
              unit={tc("units.w")}
              hint={t("results.averageHint")}
            />
            <StatTile
              label={t("results.speed")}
              value={fmt.speedKmh(result.schedule.rows.at(-1)!.distanceM, result.schedule.rows.at(-1)!.elapsedS * 1000)}
              unit={tc("units.kmh")}
            />
          </div>
          <Card
            title={t("pursuit.title")}
            as="section"
            padding="flush"
            actions={
              <ButtonLink
                to={`/tools/pursuit/board?${inputs.shareSearch(PURSUIT_KEYS, { time: true })}`}
                variant="secondary"
                size="sm"
                icon={<MonitorPlay aria-hidden />}
              >
                {t("pursuit.board")}
              </ButtonLink>
            }
          >
            <p className="tools-card-description">{t("pursuit.description")}</p>
            <DataTable
              columns={columns}
              rows={result.schedule.rows}
              getRowId={(row) => String(row.halfLap)}
              caption={t("pursuit.caption")}
              rowTone={(row) => (row.lap === null ? "muted" : undefined)}
              layout="table"
              dense
            />
          </Card>
        </>
      )}

      <CompareEffort onChange={setElapsedByLap} />
      <RiderCard inputs={inputs} />
      <ConditionsCard inputs={inputs} />
    </div>
  );
}

function CompareEffort({ onChange }: { onChange: (elapsedByLap: number[] | null) => void }) {
  const { t } = useTranslation("tools");
  const fmt = useFormat();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const sessions = useSessions(athleteId);
  const [sessionId, setSessionId] = useState("");
  const [effortIndex, setEffortIndex] = useState("");
  const efforts = useSessionEfforts(athleteId, sessionId);
  const candidates = (efforts.data ?? []).filter((effort) => effort.completed_lap_count >= MIN_COMPARE_LAPS);

  if (!sessions.data || sessions.data.length === 0) return null;

  const pickEffort = (value: string) => {
    setEffortIndex(value);
    const effort = candidates.find((candidate) => String(candidate.index) === value);
    onChange(effort ? effortElapsedByLap(effort.lap_times_ms) : null);
  };

  return (
    <Card title={t("pursuit.compare")} as="section">
      <p className="tools-card-description tools-card-description--inset">{t("pursuit.compareHint")}</p>
      <div className="tools-grid">
        <Select
          label={t("pursuit.session")}
          value={sessionId}
          onChange={(event) => {
            setSessionId(event.target.value);
            pickEffort("");
          }}
        >
          <option value="">{t("pursuit.chooseSession")}</option>
          {sessions.data.map((session) => (
            <option key={session.external_event_id} value={session.external_event_id}>
              {fmt.date(session.event_date)} · {session.event_name}
            </option>
          ))}
        </Select>
        {sessionId !== "" && efforts.data && (
          candidates.length === 0 ? (
            <p className="tools-note">{t("pursuit.noEfforts")}</p>
          ) : (
            <Select label={t("pursuit.effort")} value={effortIndex} onChange={(event) => pickEffort(event.target.value)}>
              <option value="">{t("pursuit.chooseEffort")}</option>
              {candidates.map((effort) => (
                <option key={effort.index} value={String(effort.index)}>
                  {effort.label ??
                    t("pursuit.effortOption", {
                      track: effort.track_name,
                      laps: effort.completed_lap_count,
                      time: fmt.lapTime(effort.total_time_ms),
                    })}
                </option>
              ))}
            </Select>
          )
        )}
      </div>
    </Card>
  );
}
