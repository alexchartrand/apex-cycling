import { useTranslation } from "react-i18next";
import { Card } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import type { ZoneDistribution } from "./types";

const POWER_ZONE_KEYS = ["z1", "z2", "z3", "z4", "z5", "z6", "z7"] as const;
const HR_ZONE_KEYS = ["z1", "z2", "z3", "z4", "z5"] as const;

/** Time spent in each zone as proportional bars (plain markup: they read well at any size). */
export function ZoneBars({
  kind,
  zones,
  unit,
}: {
  kind: "power" | "hr";
  zones: ZoneDistribution;
  unit: string;
}) {
  const { t } = useTranslation("activities");
  const fmt = useFormat();
  const total = zones.seconds.reduce((a, b) => a + b, 0);
  const names = kind === "power" ? POWER_ZONE_KEYS : HR_ZONE_KEYS;

  return (
    <Card as="section" title={t(kind === "power" ? "activity.zones.power" : "activity.zones.hr")}>
      <ul className="zone-bars">
        {zones.seconds.map((seconds, index) => {
          const key = names[index];
          const upper = zones.limits[index];
          const range =
            upper == null
              ? t("activity.zones.above", { value: `${fmt.number(zones.limits[index - 1], 0)} ${unit}` })
              : t("activity.zones.upTo", { value: `${fmt.number(upper, 0)} ${unit}` });
          const name = kind === "power" ? t(`activity.zones.powerNames.${key}`) : t(`activity.zones.hrNames.${key as (typeof HR_ZONE_KEYS)[number]}`);
          const share = total > 0 ? seconds / total : 0;
          return (
            <li key={key} className="zone-bars__row">
              <span className="zone-bars__name">
                <strong>{t("activity.zones.zone", { n: index + 1 })}</strong> {name}
                <span className="zone-bars__range">{range}</span>
              </span>
              <span className="zone-bars__track" aria-hidden>
                <span className="zone-bars__fill" style={{ width: `${share * 100}%`, background: `var(--chart-${(index % 6) + 1})` }} />
              </span>
              <span className="zone-bars__value">
                {fmt.duration(seconds)} <span className="zone-bars__share">{fmt.number(share * 100, 0)}%</span>
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
