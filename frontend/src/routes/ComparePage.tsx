import { GitCompare } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { EmptyState, PageHeader, SkeletonGroup } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { pickEffort } from "../features/compare/compare";
import { CompareView } from "../features/compare/CompareView";
import { EffortPicker } from "../features/compare/EffortPicker";
import { useSessionEfforts, useSessions } from "../features/training/useTraining";
import "../features/compare/Compare.css";

/** Two efforts (of one session or two) overlaid; both sides live in the URL (`?a=&ae=&b=&be=`) so a link reproduces the screen. */
export function ComparePage() {
  const { t } = useTranslation("compare");
  const { t: tt } = useTranslation("training");
  const [params, setParams] = useSearchParams();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const sessions = useSessions(athleteId);

  const eventA = params.get("a") ?? "";
  const eventB = params.get("b") ?? "";
  const effortsA = useSessionEfforts(athleteId, eventA);
  const effortsB = useSessionEfforts(athleteId, eventB);
  const effortA = effortsA.data ? pickEffort(effortsA.data, params.get("ae")) : undefined;
  const effortB = effortsB.data ? pickEffort(effortsB.data, params.get("be")) : undefined;

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  }

  const nameOf = (side: "A" | "B") => t("side", { side });
  const bothChosen = effortA && effortB && !(eventA === eventB && effortA.lap_ids[0] === effortB.lap_ids[0]);

  return (
    <>
      <PageHeader title={t("title")} eyebrow={t("eyebrow")} />
      <p className="compare-note">{t("intro")}</p>

      {sessions.isLoading && <SkeletonGroup lines={4} />}
      {sessions.data && (
        <div className="compare-pickers">
          <EffortPicker
            title={nameOf("A")}
            sessions={sessions.data}
            eventId={eventA}
            efforts={effortsA.data}
            selected={effortA}
            onSession={(id) => update({ a: id, ae: null })}
            onEffort={(id) => update({ ae: id })}
          />
          <EffortPicker
            title={nameOf("B")}
            sessions={sessions.data}
            eventId={eventB}
            efforts={effortsB.data}
            selected={effortB}
            onSession={(id) => update({ b: id, be: null })}
            onEffort={(id) => update({ be: id })}
          />
        </div>
      )}
      {(effortsA.isError || effortsB.isError) && <p role="alert">{tt("session.loadError")}</p>}

      {bothChosen ? (
        <CompareView a={effortA} b={effortB} nameA={nameOf("A")} nameB={nameOf("B")} />
      ) : (
        sessions.data && <EmptyState compact icon={<GitCompare aria-hidden />} title={effortA && effortB ? t("sameEffort") : t("pickTwo")} />
      )}
    </>
  );
}
