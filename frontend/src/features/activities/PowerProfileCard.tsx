import { useState } from "react";
import { Gauge } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Card, SkeletonGroup, StatTile, useToast } from "../../components/ui";
import { localIsoDate } from "../../i18n/format";
import { useFormat } from "../../i18n/useFormat";
import { useCurrentMetrics, useRecordMetrics } from "../athletes/useAthlete";
import { durationLabel } from "./format";
import { dismiss, fitIsTrustworthy, isDismissed, PROFILE_DAYS, suggestedFtp, wPrimeKj } from "./powerProfile";
import { usePowerProfile } from "./useActivities";
import { useQueryClient } from "@tanstack/react-query";

/** Critical power and W′ from the recent best efforts, and the FTP they suggest. */
export function PowerProfileCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("activities");
  const fmt = useFormat();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const profile = usePowerProfile(athleteId, PROFILE_DAYS);
  const weight = useCurrentMetrics(athleteId).data?.weight_kg?.value ?? null;
  const record = useRecordMetrics(athleteId);
  const [, rerender] = useState(0);

  if (profile.isLoading) return <SkeletonGroup lines={3} />;
  if (!profile.data) return null;

  const fit = profile.data.critical_power;
  const watts = suggestedFtp(profile.data);
  const showSuggestion = watts != null && !isDismissed(athleteId, watts);

  async function applySuggestion() {
    if (watts == null) return;
    try {
      await record.mutateAsync({ effective_date: localIsoDate(), ftp_w: watts });
      // The new FTP changes every ride's TSS and the load model.
      for (const key of ["power-profile", "training-load", "activity-analysis", "activities"]) {
        await queryClient.invalidateQueries({ queryKey: [key] });
      }
      toast({ title: t("profile.updated", { watts }), tone: "success" });
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  return (
    <Card title={t("profile.title")} className="power-profile">
      <p className="ui-card__hint">{t("profile.description", { days: profile.data.days })}</p>
      {showSuggestion && profile.data.ftp_suggestion && (
        <div className="power-profile__suggestion" role="status">
          <p>
            {profile.data.ftp_current_w == null
              ? t("profile.suggestNone", { watts })
              : t("profile.suggest", { watts, current: fmt.number(profile.data.ftp_current_w, 0) })}{" "}
            <span className="power-profile__basis">
              {t("profile.basis", {
                duration: durationLabel(profile.data.ftp_suggestion.source_duration_s),
                power: fmt.number(profile.data.ftp_suggestion.source_power_w, 0),
              })}
            </span>
          </p>
          <div className="power-profile__actions">
            <Button size="sm" onClick={applySuggestion} loading={record.isPending}>
              {t("profile.update", { watts })}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                dismiss(athleteId, watts!);
                rerender((n) => n + 1);
              }}
            >
              {t("profile.notNow")}
            </Button>
          </div>
        </div>
      )}

      {fit ? (
        <>
          <div className="power-profile__tiles">
            <StatTile
              icon={<Gauge aria-hidden />}
              label={t("profile.cp")}
              value={fmt.number(fit.cp_w, 0)}
              unit="W"
              hint={weight ? t("profile.perKg", { value: fmt.number(fit.cp_w / weight, 2, 2) }) : undefined}
            />
            <StatTile label={t("profile.wPrime")} value={fmt.number(wPrimeKj(fit.w_prime_j), 1)} unit="kJ" />
            {profile.data.ftp_current_w != null && (
              <StatTile label={t("profile.ftp")} value={fmt.number(profile.data.ftp_current_w, 0)} unit="W" />
            )}
          </div>
          <p className="ui-card__hint">
            {t("profile.fitNote", { points: fit.points, r2: fmt.number(fit.r_squared, 3, 3) })}
            {!fitIsTrustworthy(profile.data) && ` ${t("profile.fitLoose")}`}
          </p>
        </>
      ) : (
        <p className="ui-card__hint">{t("profile.noFit")}</p>
      )}
    </Card>
  );
}
