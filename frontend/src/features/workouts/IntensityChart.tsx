import { useTranslation } from "react-i18next";
import { useFormat } from "../../i18n/useFormat";
import { clockText, lengthText, profileBars, profileScale, timeTicks } from "./profile";
import type { ProfileSegment } from "./types";

const WIDTH = 1000;
const HEIGHT = 200;
// A sprint of a few seconds in an hour-long workout would be invisible.
const MIN_BAR_WIDTH = 2;

/** The workout as ridden: a bar per step, height = intensity (fraction of FTP), FTP dashed. */
export function IntensityChart({ segments }: { segments: ProfileSegment[] }) {
  const { t } = useTranslation("workouts");
  const fmt = useFormat();
  const scale = profileScale(segments);
  const bars = profileBars(segments, scale);
  const total = segments.reduce((end, segment) => Math.max(end, segment.start_s + segment.duration_s), 0);
  if (bars.length === 0) return <p className="workout-chart__empty">{t("chart.empty")}</p>;

  const ftpY = HEIGHT * (1 - 1 / scale);
  const describe = (segment: ProfileSegment) => {
    const name = segment.label ?? t(`kinds.${segment.kind}`);
    const intensity =
      segment.power_low != null && segment.power_high != null && segment.power_high > segment.power_low
        ? `${fmt.number(segment.power_low * 100, 0)}–${fmt.number(segment.power_high * 100, 0)} %`
        : segment.intensity != null
          ? `${fmt.number(segment.intensity * 100, 0)} %`
          : t("chart.unrated");
    return `${name} · ${clockText(segment.duration_s)} · ${intensity}`;
  };

  return (
    <figure className="workout-chart">
      <div className="workout-chart__plot">
        <svg
          className="workout-chart__svg"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={t("chart.label", { duration: lengthText(total) })}
        >
          {bars.map((bar, index) => {
            const x = bar.x * WIDTH;
            const width = Math.max(MIN_BAR_WIDTH, bar.width * WIDTH);
            const top = HEIGHT * (1 - bar.height);
            return (
              <g key={index} className={`workout-chart__bar workout-chart__bar--${bar.tone}${bar.unrated ? " workout-chart__bar--unrated" : ""}`}>
                <title>{describe(bar.segment)}</title>
                <rect x={x} y={top} width={width} height={HEIGHT - top} />
                {bar.rangeLow != null && (
                  <rect className="workout-chart__range" x={x} y={top} width={width} height={HEIGHT * (bar.height - bar.rangeLow)} />
                )}
              </g>
            );
          })}
          <line className="workout-chart__ftp" x1={0} x2={WIDTH} y1={ftpY} y2={ftpY} vectorEffect="non-scaling-stroke" />
        </svg>
        <span className="workout-chart__ftp-label" style={{ top: `${(ftpY / HEIGHT) * 100}%` }}>
          {t("chart.ftp")}
        </span>
      </div>
      <div className="workout-chart__axis" aria-hidden>
        {timeTicks(total).map((tick) => (
          <span key={tick} style={{ left: `${(tick / total) * 100}%` }}>
            {clockText(tick)}
          </span>
        ))}
      </div>
    </figure>
  );
}
