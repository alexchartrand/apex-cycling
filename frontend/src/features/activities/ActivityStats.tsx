import { Activity as ActivityIcon, Clock, Gauge, HeartPulse, Mountain, Route, Timer, Zap } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { StatTile } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { mpsToKmh } from "./format";
import type { Activity, ActivityAnalysis } from "./types";

/** The headline numbers of a ride; power and heart-rate tiles appear only when the recording has them. */
export function ActivityStats({ activity, analysis }: { activity: Activity; analysis?: ActivityAnalysis }) {
  const { t } = useTranslation("activities");
  const fmt = useFormat();
  const tiles: ReactNode[] = [];
  const add = (key: string, node: ReactNode) => tiles.push(<div key={key}>{node}</div>);

  const hours = activity.elapsed_s >= 3600;
  add(
    "duration",
    <StatTile
      label={t("activity.stats.duration")}
      icon={<Clock aria-hidden />}
      value={fmt.duration(activity.elapsed_s)}
      unit={hours ? "h" : "min"}
      hint={activity.moving_s && Math.abs(activity.moving_s - activity.elapsed_s) > 30 ? `${t("activity.stats.moving")} ${fmt.duration(activity.moving_s)}` : undefined}
    />,
  );
  if (activity.distance_m != null) {
    add(
      "distance",
      <StatTile
        label={t("activity.stats.distance")}
        icon={<Route aria-hidden />}
        value={fmt.number(activity.distance_m / 1000, 1)}
        unit="km"
      />,
    );
  }
  const speed = mpsToKmh(activity.avg_speed_mps);
  if (speed != null) {
    add("speed", <StatTile label={t("activity.stats.avgSpeed")} icon={<Gauge aria-hidden />} value={fmt.number(speed, 1)} unit="km/h" />);
  }
  if (activity.elevation_gain_m != null && activity.elevation_gain_m >= 1) {
    add("elevation", <StatTile label={t("activity.stats.elevation")} icon={<Mountain aria-hidden />} value={fmt.number(activity.elevation_gain_m, 0)} unit="m" />);
  }

  if (activity.has_power) {
    add(
      "power",
      <StatTile
        label={t("activity.stats.avgPower")}
        icon={<Zap aria-hidden />}
        tone="accent"
        value={fmt.number(activity.avg_power_w, 0)}
        unit="W"
        hint={analysis?.avg_power_w_per_kg != null ? `${fmt.number(analysis.avg_power_w_per_kg, 2)} W/kg` : undefined}
      />,
    );
    if (activity.normalized_power_w != null) {
      add(
        "np",
        <StatTile
          label={t("activity.stats.normalizedPower")}
          icon={<Zap aria-hidden />}
          value={fmt.number(activity.normalized_power_w, 0)}
          unit="W"
          hint={analysis?.variability_index != null ? `VI ${fmt.number(analysis.variability_index, 2, 2)}` : undefined}
        />,
      );
    }
    add("max-power", <StatTile label={t("activity.stats.maxPower")} icon={<Zap aria-hidden />} value={fmt.number(activity.max_power_w, 0)} unit="W" />);
    if (analysis?.intensity_factor != null) {
      add("if", <StatTile label={t("activity.stats.intensityFactor")} icon={<ActivityIcon aria-hidden />} value={fmt.number(analysis.intensity_factor, 2, 2)} />);
    }
    if (activity.tss != null) {
      add("tss", <StatTile label={t("activity.stats.tss")} icon={<Timer aria-hidden />} tone="highlight" value={fmt.number(activity.tss, 0)} hint="TSS" />);
    }
    if (analysis?.work_kj != null) {
      add("work", <StatTile label={t("activity.stats.work")} icon={<Zap aria-hidden />} value={fmt.number(analysis.work_kj, 0)} unit="kJ" />);
    }
  }
  if (activity.has_heart_rate) {
    add(
      "hr",
      <StatTile
        label={t("activity.stats.avgHeartRate")}
        icon={<HeartPulse aria-hidden />}
        value={fmt.number(activity.avg_heart_rate, 0)}
        unit="bpm"
        hint={activity.max_heart_rate != null ? `${t("activity.stats.maxHeartRate")} ${fmt.number(activity.max_heart_rate, 0)}` : undefined}
      />,
    );
  }
  if (activity.has_cadence && activity.avg_cadence != null) {
    add("cadence", <StatTile label={t("activity.stats.avgCadence")} icon={<ActivityIcon aria-hidden />} value={fmt.number(activity.avg_cadence, 0)} unit="rpm" />);
  }

  return <div className="activity-stats">{tiles}</div>;
}
