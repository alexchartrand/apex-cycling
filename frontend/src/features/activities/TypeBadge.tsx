import { useTranslation } from "react-i18next";
import { ACTIVITY_TYPES, typeIcon } from "./activityTypes";
import type { ActivityType } from "./types";
import "./ActivityTypes.css";

/** The activity type as a coloured pill with its icon. */
export function TypeBadge({ type, short = false }: { type: ActivityType; short?: boolean }) {
  const { t } = useTranslation("activities");
  const Icon = typeIcon(type);
  return (
    <span className={`type-badge type-${type}`}>
      <Icon aria-hidden />
      {t(short ? `types.${type}.short` : `types.${type}.name`)}
    </span>
  );
}

/** One toggle per type, coloured like the log; `shown` null = everything. */
export function TypeLegend({ shown, onToggle }: { shown: Set<ActivityType> | null; onToggle: (type: ActivityType) => void }) {
  const { t } = useTranslation("activities");
  return (
    <div className="type-legend" role="group" aria-label={t("log.filter")}>
      <span className="type-legend__label">{t("log.filter")}</span>
      {ACTIVITY_TYPES.map((type) => (
        <button
          key={type}
          type="button"
          className={`type-legend__toggle type-${type}`}
          aria-pressed={shown !== null && shown.has(type)}
          onClick={() => onToggle(type)}
        >
          <span className="type-legend__dot" aria-hidden />
          {t(`types.${type}.name`)}
        </button>
      ))}
    </div>
  );
}
