import { Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, DataTable, EmptyState, Select, SkeletonGroup, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import { useViewAthlete } from "../athletes/useViewAthlete";
import { gapToShow, splitSquad } from "./squad";
import type { SquadRow } from "./types";
import { useSquad } from "./useCoaching";

/** Every athlete I coach, ranked by their best at one event — sqorz laps and hand-entered results only. */
export function SquadPanel() {
  const { t } = useTranslation("coach");
  const { t: tr } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const view = useViewAthlete();
  const [eventKey, setEventKey] = useState<StandardEventKey>("1km");
  const [startType, setStartType] = useState<"standing" | "flying">("standing");
  const [trackId, setTrackId] = useState("");
  const squad = useSquad(eventKey, startType, trackId);
  const allowedStarts = EVENT_START_TYPES[eventKey];

  const columns: DataTableColumn<SquadRow>[] = [
    { id: "rank", header: t("squad.rank"), cell: (row) => row.rank ?? "—", sortValue: (row) => row.rank ?? 999, width: "4rem", primary: true },
    {
      id: "athlete",
      header: t("squad.athlete"),
      cell: (row) => (
        <button type="button" className="squad__name" onClick={() => view(row.athlete_id)}>
          {row.athlete_name}
        </button>
      ),
      sortValue: (row) => row.athlete_name.toLowerCase(),
    },
    { id: "time", header: t("squad.time"), align: "right", cell: (row) => (row.time_ms == null ? "—" : formatRecordTime(row.time_ms, fmt)), sortValue: (row) => row.time_ms ?? Number.MAX_SAFE_INTEGER },
    {
      id: "gap",
      header: t("squad.gap"),
      align: "right",
      cell: (row) => {
        const gap = gapToShow(row);
        return gap == null ? "" : `+${fmt.seconds(gap)} s`;
      },
      sortValue: (row) => row.gap_ms ?? Number.MAX_SAFE_INTEGER,
      hideOnMobile: true,
    },
    {
      id: "place",
      header: t("squad.place"),
      cell: (row) =>
        row.place ? (
          <span>
            {row.place} {row.source === "manual" && <Badge>{t("squad.manual")}</Badge>}
          </span>
        ) : (
          ""
        ),
      sortValue: (row) => row.place ?? "",
      hideOnMobile: true,
    },
    { id: "date", header: t("squad.date"), cell: (row) => (row.achieved_on ? fmt.date(row.achieved_on, "medium") : ""), sortValue: (row) => row.achieved_on ?? "", hideOnMobile: true },
  ];

  const { ranked, unranked } = splitSquad(squad.data?.rows ?? []);

  return (
    <div className="coach-stack">
      <Card title={t("squad.title")} as="section">
        <p className="coach-muted">{t("squad.description")}</p>
        <div className="squad__filters">
          <Select
            label={t("squad.event")}
            value={eventKey}
            onChange={(e) => {
              const next = e.target.value as StandardEventKey;
              setEventKey(next);
              if (!EVENT_START_TYPES[next].includes(startType)) setStartType(EVENT_START_TYPES[next][0]);
            }}
          >
            {STANDARD_EVENT_KEYS.map((key) => (
              <option key={key} value={key}>
                {tr(`events.${key}`)}
              </option>
            ))}
          </Select>
          <Select label={t("squad.start")} value={startType} disabled={allowedStarts.length === 1} onChange={(e) => setStartType(e.target.value as "standing" | "flying")}>
            {allowedStarts.map((start) => (
              <option key={start} value={start}>
                {tr(`startTypes.${start}`)}
              </option>
            ))}
          </Select>
          <Select label={t("squad.track")} value={trackId} onChange={(e) => setTrackId(e.target.value)}>
            <option value="">{t("squad.anyTrack")}</option>
            {squad.data?.tracks.map((track) => (
              <option key={track.id} value={track.id}>
                {track.name}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      {squad.isLoading && <SkeletonGroup lines={4} />}
      {squad.isError && <p role="alert">{tc("loadError")}</p>}
      {squad.data && squad.data.rows.length === 0 && (
        <EmptyState compact icon={<Users aria-hidden />} title={t("squad.emptyTitle")} description={t("squad.emptyDescription")} />
      )}
      {squad.data && squad.data.rows.length > 0 && (
        <Card padding="flush" as="section">
          <DataTable
            caption={t("squad.caption", { event: tr(`events.${eventKey}`) })}
            columns={columns}
            rows={[...ranked, ...unranked]}
            getRowId={(row) => row.athlete_id}
            initialSort={{ columnId: "rank", direction: "asc" }}
            empty={<p className="coach-muted">{t("squad.noTimes")}</p>}
          />
        </Card>
      )}
    </div>
  );
}
