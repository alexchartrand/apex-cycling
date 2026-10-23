import { useState, type FormEvent } from "react";
import { GitCompare, Pencil } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../../api/errors";
import { Badge, Button, ButtonLink, Card, Dialog, IconButton, Input, StatTile, Tooltip, useToast, type BadgeTone } from "../../../components/ui";
import { useFormat } from "../../../i18n/useFormat";
import { GearPicker } from "../../equipment/GearPicker";
import { useEffortGear } from "../../equipment/useEquipment";
import type { Bike } from "../../equipment/types";
import type { Effort, StartType } from "../types";
import { useLabelEffort } from "../useTraining";
import { effortCardModel } from "../../share/cardModels";
import { ShareButton } from "../../share/ShareButton";
import { compareHref } from "../../compare/compare";
import { HalfLapSplitChart } from "./HalfLapSplitChart";
import { PacingChart } from "./PacingChart";
import "./EffortCard.css";

const START_TONES: Record<StartType, BadgeTone> = { standing: "highlight", flying: "accent", unknown: "neutral" };

export function EffortCard({
  athleteId,
  eventId,
  effort,
  bikes,
  date,
  trackLengthM = null,
}: {
  athleteId: string;
  eventId: string;
  effort: Effort;
  bikes: Bike[];
  /** The session's date, for the share card. */
  date?: string;
  trackLengthM?: number | null;
}) {
  const { t } = useTranslation("training");
  const { t: tg } = useTranslation("equipment");
  const effortGear = useEffortGear(athleteId, eventId);
  const { t: tr } = useTranslation("records");
  const { t: ts } = useTranslation("share");
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
        <>
          {effort.total_time_ms != null && date && (
            <ShareButton
              buildModel={() =>
                effortCardModel(
                  { effort, date, trackLengthM },
                  {
                    brand: ts("brand"),
                    eyebrow: ts("effort", { start: tr(`startTypes.${effort.start_type}`) }),
                    title: effort.label ?? t("efforts.effortN", { n: effort.index }),
                    splitsCaption: ts("splits"),
                    deltaNote: effort.avg_speed_kmh != null ? ts("average", { speed: fmt.number(effort.avg_speed_kmh, 1, 1) }) : null,
                  },
                  fmt,
                )
              }
            />
          )}
          <Tooltip content={t("efforts.compare")}>
            <ButtonLink
              to={compareHref({ eventId, firstLapId: effort.lap_ids[0] })}
              variant="ghost"
              className="btn--icon"
              aria-label={t("efforts.compare")}
            >
              <GitCompare aria-hidden />
            </ButtonLink>
          </Tooltip>
          <Tooltip content={t("efforts.rename")}>
            <IconButton aria-label={t("efforts.rename")} variant="ghost" onClick={() => setRenaming(true)}>
              <Pencil aria-hidden />
            </IconButton>
          </Tooltip>
        </>
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
        {effort.est_cadence_rpm != null && (
          <StatTile label={t("efforts.estCadence")} value={fmt.number(effort.est_cadence_rpm, 0)} unit="rpm" />
        )}
      </div>
      {(effort.peak_speed_kmh != null || effort.launch_accel_ms2 != null || effort.pacing?.cv_pct != null || effort.pacing?.fade_pct != null) && (
        <div className="effort-card__stats">
          {effort.peak_speed_kmh != null && (
            <StatTile label={t("efforts.topSpeed")} value={fmt.number(effort.peak_speed_kmh, 1, 1)} unit="km/h" hint={t("efforts.topSpeedHint")} />
          )}
          {effort.launch_accel_ms2 != null && effort.launch_time_ms != null && effort.launch_distance_m != null && (
            <StatTile
              label={t("efforts.launch")}
              value={fmt.seconds(effort.launch_time_ms, 2)}
              unit="s"
              hint={t("efforts.launchHint", { distance: fmt.distance(effort.launch_distance_m), accel: fmt.number(effort.launch_accel_ms2, 1, 1) })}
            />
          )}
          {effort.pacing?.cv_pct != null && (
            <StatTile label={t("efforts.consistency")} value={fmt.number(effort.pacing.cv_pct, 1, 1)} unit="%" hint={t("efforts.consistencyHint")} />
          )}
          {effort.pacing?.fade_pct != null && (
            <StatTile
              label={t("efforts.fade")}
              value={`${effort.pacing.fade_pct > 0 ? "+" : ""}${fmt.number(effort.pacing.fade_pct, 1, 1)}`}
              unit="%"
              hint={t("efforts.fadeHint")}
            />
          )}
        </div>
      )}
      {bikes.some((bike) => bike.gears.length > 0) && (
        <GearPicker
          bikes={bikes}
          value={effort.gear_setup_id ?? null}
          onChange={(gearId) => effortGear.mutateAsync({ firstLapId: effort.lap_ids[0], gearId })}
          label={tg("picker.effort")}
          emptyLabel={tg("picker.sameAsSession")}
          pending={effortGear.isPending}
          error={effortGear.error}
        />
      )}
      {hasUnfinishedLap && <p className="effort-card__note">{t("efforts.unfinishedNote")}</p>}

      {effort.pacing && (
        <section aria-label={t("efforts.pacingTitle")}>
          <h4 className="effort-card__subtitle">{t("efforts.pacingTitle")}</h4>
          <p className="effort-card__note">
            {effort.pacing.start_lap_skipped ? t("efforts.pacingHintStanding") : t("efforts.pacingHint")}
          </p>
          <PacingChart effort={effort} pacing={effort.pacing} />
        </section>
      )}

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
