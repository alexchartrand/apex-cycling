import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Download, Eye, EyeOff, Tag } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../../api/errors";
import {
  Badge,
  Button,
  Card,
  DataTable,
  Dialog,
  IconButton,
  Input,
  Tooltip,
  useToast,
  type DataTableColumn,
} from "../../../components/ui";
import { PHONE_QUERY, useMediaQuery } from "../../../hooks/useMediaQuery";
import { useFormat } from "../../../i18n/useFormat";
import { lapSpeedKmh, lapsToCsv, recordingColumns, splitColumns, splitMs } from "../lapTable";
import {
  DEFAULT_LAP_DISTANCE_M,
  flying200Ms,
  lapNumber,
} from "../sessionStats";
import type { LapDetail, TrackSessionDetail, TrackSummary } from "../types";
import { useUpdateLap } from "../useTraining";
import { VelodromeDiagram } from "../VelodromeDiagram";
import "./TrackLaps.css";

const SPLIT_PREFIX = "split:";
/** On a phone every lap is a card, so a long session starts collapsed to this many. */
export const PHONE_LAP_LIMIT = 12;

type LapRow = { lap: LapDetail; n: number };

function downloadCsv(filename: string, csv: string) {
  const url = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function slug(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** One track of a session as a lap table with checkpoint splits, plus the interactive track diagram. */
export function TrackLaps({
  athleteId,
  sessionTitle,
  track,
  meta,
}: {
  athleteId: string;
  sessionTitle: string;
  track: TrackSessionDetail;
  meta: TrackSummary | undefined;
}) {
  const { t } = useTranslation("training");
  const fmt = useFormat();
  const { toast } = useToast();
  const updateLap = useUpdateLap(athleteId);
  const [selectedLoopId, setSelectedLoopId] = useState<string | null>(null);
  const [labelling, setLabelling] = useState<LapRow | null>(null);
  const [showAllLaps, setShowAllLaps] = useState(false);
  const isPhone = useMediaQuery(PHONE_QUERY);

  const lengthM = meta?.length_m;
  const speedLengthM = lengthM ?? DEFAULT_LAP_DISTANCE_M;
  const hiddenLoopIds = useMemo(
    () =>
      new Set(
        (meta?.loops ?? [])
          .filter((loop) => loop.hidden)
          .map((loop) => loop.id),
      ),
    [meta],
  );
  const columns = useMemo(
    () => splitColumns(track.laps, hiddenLoopIds),
    [track.laps, hiddenLoopIds],
  );
  const recorded = useMemo(() => recordingColumns(track.laps), [track.laps]);
  const rows = useMemo(
    () => track.laps.map((lap, index) => ({ lap, n: lapNumber(lap, index) })),
    [track.laps],
  );
  const collapsed = isPhone && !showAllLaps && rows.length > PHONE_LAP_LIMIT;
  const visibleRows = collapsed ? rows.slice(0, PHONE_LAP_LIMIT) : rows;
  const highlighted =
    selectedLoopId && columns.some((c) => c.loopId === selectedLoopId)
      ? `${SPLIT_PREFIX}${selectedLoopId}`
      : null;
  const tableRef = useRef<HTMLDivElement>(null);

  // The table scrolls sideways; bring the picked checkpoint's column into view.
  useEffect(() => {
    if (highlighted) {
      tableRef.current
        ?.querySelector(".data-table__col--highlight")
        ?.scrollIntoView({
          inline: "center",
          block: "nearest",
          behavior: "smooth",
        });
    }
  }, [highlighted]);

  const tableColumns: DataTableColumn<LapRow>[] = [
    {
      id: "lap",
      header: t("laps.number"),
      primary: true,
      cell: ({ lap, n }) => (
        <span className="track-laps__lap">
          {n}
          {lap.excluded && <Badge>{t("laps.excludedBadge")}</Badge>}
          {lap.label && <span className="track-laps__label">{lap.label}</span>}
        </span>
      ),
      sortValue: ({ n }) => n,
    },
    {
      id: "start",
      header: t("laps.start"),
      cell: ({ lap }) => fmt.time(lap.start_time),
      sortValue: ({ lap }) => lap.start_time,
      hideOnMobile: true,
    },
    {
      id: "time",
      header: t("laps.time"),
      align: "right",
      cell: ({ lap }) => fmt.lapTime(lap.whole_lap_time_ms),
      sortValue: ({ lap }) => lap.whole_lap_time_ms,
    },
    {
      id: "speed",
      header: `${t("laps.speed")} (km/h)`,
      align: "right",
      cell: ({ lap }) => fmt.number(lapSpeedKmh(lap, speedLengthM), 1, 1),
      sortValue: ({ lap }) => lapSpeedKmh(lap, speedLengthM),
    },
    {
      id: "f200",
      header: `${t("laps.f200")} (s)`,
      align: "right",
      cell: ({ lap }) => fmt.seconds(flying200Ms(lap)),
      sortValue: ({ lap }) => flying200Ms(lap),
    },
    ...(recorded.power
      ? [
          {
            id: "power",
            header: `${t("laps.power")} (W)`,
            align: "right" as const,
            cell: ({ lap }: LapRow) => fmt.number(lap.avg_power_w, 0),
            sortValue: ({ lap }: LapRow) => lap.avg_power_w,
          },
        ]
      : []),
    ...(recorded.heartRate
      ? [
          {
            id: "heartRate",
            header: `${t("laps.heartRate")} (bpm)`,
            align: "right" as const,
            cell: ({ lap }: LapRow) => fmt.number(lap.avg_heart_rate, 0),
            sortValue: ({ lap }: LapRow) => lap.avg_heart_rate,
            hideOnMobile: true,
          },
        ]
      : []),
    ...(recorded.cadence
      ? [
          {
            id: "cadence",
            header: `${t("laps.cadence")} (rpm)`,
            align: "right" as const,
            cell: ({ lap }: LapRow) => fmt.number(lap.avg_cadence, 0),
            sortValue: ({ lap }: LapRow) => lap.avg_cadence,
            hideOnMobile: true,
          },
        ]
      : []),
    ...(recorded.estCadence
      ? [
          {
            id: "estCadence",
            header: `${t("laps.estCadence")} (rpm)`,
            align: "right" as const,
            cell: ({ lap }: LapRow) => fmt.number(lap.est_cadence_rpm, 0),
            sortValue: ({ lap }: LapRow) => lap.est_cadence_rpm,
            hideOnMobile: true,
          },
        ]
      : []),
    ...columns.map((column): DataTableColumn<LapRow> => ({
      id: `${SPLIT_PREFIX}${column.loopId}`,
      header: `${column.name} (s)`,
      align: "right",
      cell: ({ lap }) => fmt.seconds(splitMs(lap, column.loopId)),
      sortValue: ({ lap }) => splitMs(lap, column.loopId),
      hideOnMobile: true,
    })),
    {
      id: "actions",
      header: <span className="visually-hidden">{t("laps.actions")}</span>,
      align: "right",
      cell: (row) => (
        <span className="track-laps__actions">
          <Tooltip content={t("laps.editLabel", { n: row.n })}>
            <IconButton
              size="sm"
              aria-label={t("laps.editLabel", { n: row.n })}
              onClick={() => setLabelling(row)}
            >
              <Tag aria-hidden />
            </IconButton>
          </Tooltip>
          <Tooltip
            content={
              row.lap.excluded
                ? t("laps.include", { n: row.n })
                : t("laps.exclude", { n: row.n })
            }
          >
            <IconButton
              size="sm"
              aria-label={
                row.lap.excluded
                  ? t("laps.include", { n: row.n })
                  : t("laps.exclude", { n: row.n })
              }
              aria-pressed={row.lap.excluded}
              disabled={updateLap.isPending}
              onClick={() =>
                updateLap.mutate({
                  lapId: row.lap.lap_id,
                  excluded: !row.lap.excluded,
                })
              }
            >
              {row.lap.excluded ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
            </IconButton>
          </Tooltip>
        </span>
      ),
      width: "6rem",
    },
  ];

  return (
    <Card
      eyebrow={t("session.track")}
      title={track.track_name}
      actions={
        <Button
          size="sm"
          variant="secondary"
          icon={<Download aria-hidden />}
          onClick={() =>
            downloadCsv(
              `${slug(sessionTitle)}-${slug(track.track_name)}.csv`,
              lapsToCsv(track.laps, columns, speedLengthM),
            )
          }
        >
          {t("laps.exportCsv")}
        </Button>
      }
    >
      <VelodromeDiagram
        loops={meta?.loops ?? []}
        lengthM={lengthM}
        selectedLoopId={selectedLoopId}
        onSelectLoop={setSelectedLoopId}
      />
      <p className="track-laps__hint">{t("laps.diagramHint")}</p>
      {lengthM == null && (
        <p className="track-laps__hint">
          {t("session.assumedLength", {
            length: fmt.distance(DEFAULT_LAP_DISTANCE_M),
          })}
        </p>
      )}

      <div ref={tableRef}>
        <DataTable
          caption={t("laps.caption", { track: track.track_name })}
          columns={tableColumns}
          rows={visibleRows}
          getRowId={({ lap }) => lap.lap_id}
          rowTone={({ lap }) => (lap.excluded ? "muted" : undefined)}
          highlightedColumnId={highlighted}
          empty={<p className="track-laps__hint">{t("laps.empty")}</p>}
          dense
        />
      </div>
      {isPhone && rows.length > PHONE_LAP_LIMIT && (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setShowAllLaps((open) => !open)}
        >
          {collapsed
            ? t("laps.showAll", { total: rows.length })
            : t("laps.showFewer")}
        </Button>
      )}
      <p className="track-laps__hint">
        {t("laps.splitsHint")} {t("laps.excludedHint")}
      </p>

      {labelling && (
        <LabelDialog
          key={labelling.lap.lap_id}
          row={labelling}
          onClose={() => setLabelling(null)}
          save={async (label) => {
            try {
              await updateLap.mutateAsync({
                lapId: labelling.lap.lap_id,
                label,
              });
              toast({ title: t("laps.labelSaved"), tone: "success" });
              setLabelling(null);
            } catch {
              // shown inside the dialog
            }
          }}
          error={updateLap.isError ? errorMessage(updateLap.error) : null}
          pending={updateLap.isPending}
        />
      )}
    </Card>
  );
}

function LabelDialog({
  row,
  onClose,
  save,
  error,
  pending,
}: {
  row: LapRow;
  onClose: () => void;
  save: (label: string | null) => Promise<void>;
  error: string | null;
  pending: boolean;
}) {
  const { t } = useTranslation("training");
  const { t: tc } = useTranslation("common");
  const [label, setLabel] = useState(row.lap.label ?? "");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void save(label.trim() || null);
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("laps.labelTitle", { n: row.n })}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="lap-label-form" loading={pending}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="lap-label-form" onSubmit={handleSubmit}>
        <Input
          label={t("laps.labelField")}
          value={label}
          maxLength={100}
          placeholder={t("laps.labelPlaceholder")}
          onChange={(e) => setLabel(e.target.value)}
          error={error ?? undefined}
          autoFocus
        />
      </form>
    </Dialog>
  );
}
