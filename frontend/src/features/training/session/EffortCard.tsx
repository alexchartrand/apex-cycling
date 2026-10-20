import { useState, type FormEvent } from "react";
import { Pencil } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../../api/errors";
import { Badge, Button, Card, Dialog, IconButton, Input, StatTile, Tooltip, useToast, type BadgeTone } from "../../../components/ui";
import { useFormat } from "../../../i18n/useFormat";
import type { Effort, StartType } from "../types";
import { useLabelEffort } from "../useTraining";
import { HalfLapSplitChart } from "./HalfLapSplitChart";
import "./EffortCard.css";

const START_TONES: Record<StartType, BadgeTone> = { standing: "highlight", flying: "accent", unknown: "neutral" };

export function EffortCard({ athleteId, eventId, effort }: { athleteId: string; eventId: string; effort: Effort }) {
  const { t } = useTranslation("training");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();
  const [renaming, setRenaming] = useState(false);
  const hasUnfinishedLap = effort.completed_lap_count < effort.lap_ids.length;

  return (
    <Card
      eyebrow={`${effort.track_name} · ${fmt.time(effort.start_time)}`}
      title={
        <span className="effort-card__title">
          {effort.label ?? t("efforts.effortN", { n: effort.index })}
          <Badge tone={START_TONES[effort.start_type]}>{tr(`startTypes.${effort.start_type}`)}</Badge>
        </span>
      }
      actions={
        <Tooltip content={t("efforts.rename")}>
          <IconButton aria-label={t("efforts.rename")} variant="ghost" onClick={() => setRenaming(true)}>
            <Pencil aria-hidden />
          </IconButton>
        </Tooltip>
      }
    >
      <div className="effort-card__stats">
        <StatTile
          label={t("efforts.laps")}
          value={t("efforts.lapsDone", { done: effort.completed_lap_count, total: effort.lap_ids.length })}
          size="md"
        />
        <StatTile label={t("efforts.total")} value={effort.total_time_ms != null ? fmt.lapTime(effort.total_time_ms) : "—"} />
        <StatTile label={t("efforts.distance")} value={fmt.distance(effort.distance_m)} />
        <StatTile
          label={t("efforts.avgSpeed")}
          value={effort.avg_speed_kmh != null ? fmt.number(effort.avg_speed_kmh, 1, 1) : "—"}
          unit={effort.avg_speed_kmh != null ? "km/h" : undefined}
        />
        <StatTile label={t("efforts.bestLap")} tone="accent" value={fmt.lapTime(effort.best_lap_ms)} />
        {effort.avg_power_w != null && <StatTile label={t("efforts.avgPower")} value={fmt.number(effort.avg_power_w, 0)} unit="W" />}
        {effort.avg_heart_rate != null && (
          <StatTile label={t("efforts.avgHeartRate")} value={fmt.number(effort.avg_heart_rate, 0)} unit="bpm" />
        )}
      </div>
      {hasUnfinishedLap && <p className="effort-card__note">{t("efforts.unfinishedNote")}</p>}

      {effort.half_lap_splits.length > 0 && (
        <section aria-label={t("efforts.splitsTitle")}>
          <h4 className="effort-card__subtitle">{t("efforts.splitsTitle")}</h4>
          <p className="effort-card__note">{t("efforts.splitsHint")}</p>
          <HalfLapSplitChart splits={effort.half_lap_splits} />
        </section>
      )}

      {renaming && <RenameDialog athleteId={athleteId} eventId={eventId} effort={effort} onClose={() => setRenaming(false)} />}
    </Card>
  );
}

function RenameDialog({ athleteId, eventId, effort, onClose }: { athleteId: string; eventId: string; effort: Effort; onClose: () => void }) {
  const { t } = useTranslation("training");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const mutation = useLabelEffort(athleteId, eventId);
  const [label, setLabel] = useState(effort.label ?? "");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await mutation.mutateAsync({ firstLapId: effort.lap_ids[0], label: label.trim() || null });
      toast({ title: t("efforts.saved"), tone: "success" });
      onClose();
    } catch {
      // shown inside the dialog
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("efforts.renameTitle")}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="effort-label-form" loading={mutation.isPending}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="effort-label-form" onSubmit={handleSubmit}>
        <Input
          label={t("efforts.labelField")}
          value={label}
          maxLength={100}
          placeholder={t("efforts.labelPlaceholder")}
          onChange={(e) => setLabel(e.target.value)}
          error={mutation.isError ? errorMessage(mutation.error) : undefined}
          autoFocus
        />
      </form>
    </Dialog>
  );
}
