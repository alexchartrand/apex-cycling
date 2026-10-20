import { useState } from "react";
import { Wind } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/errors";
import { Button, ButtonLink, Card, EmptyState, PageHeader, Select, SkeletonGroup, StatTile, useToast } from "../components/ui";
import { useActivities } from "../features/activities/useActivities";
import { AeroInputsForm } from "../features/aero/AeroInputsForm";
import { AeroLapTable } from "../features/aero/AeroLapTable";
import { AeroScatter } from "../features/aero/AeroScatter";
import { AeroTestsCard } from "../features/aero/AeroTestsCard";
import { draftFromInputs, EMPTY_DRAFT, readInputs, sessionsWithPower, toggleLap, type InputDraft } from "../features/aero/aero";
import { SaveTestDialog } from "../features/aero/SaveTestDialog";
import type { AeroSetup, AeroTest } from "../features/aero/types";
import { useAeroEstimate, useAeroTests, useCreateAeroTest, useUpdateAeroTest } from "../features/aero/useAero";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { useSessions } from "../features/training/useTraining";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { useFormat } from "../i18n/useFormat";
import "./AeroPage.css";

/**
 * CdA from a session's laps (`?session=`, `?track=`), the laps and
 * assumptions adjustable, saved as aero tests and compared. `?test=` is the
 * saved test being edited.
 */
export function AeroPage() {
  const { t } = useTranslation(["aero", "common"]);
  const fmt = useFormat();
  const { toast } = useToast();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const [params, setParams] = useSearchParams();

  const sessions = useSessions(athleteId);
  const activities = useActivities(athleteId);
  const tests = useAeroTests(athleteId);
  const createTest = useCreateAeroTest(athleteId);
  const updateTest = useUpdateAeroTest(athleteId);

  const candidates = sessionsWithPower(sessions.data ?? [], activities.data ?? []);
  const eventId = params.get("session") ?? candidates[0]?.external_event_id ?? "";
  const trackId = params.get("track");
  const editing = tests.data?.find((test) => test.id === params.get("test")) ?? null;

  const [draft, setDraft] = useState<InputDraft>(EMPTY_DRAFT);
  const [lapIds, setLapIds] = useState<string[] | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const { inputs, invalid } = readInputs(draft);
  const settledInputs = useDebouncedValue(inputs, 400);
  const estimate = useAeroEstimate(athleteId, eventId, { ...settledInputs, track_id: trackId, lap_ids: lapIds });
  const result = estimate.data?.external_event_id === eventId ? estimate.data : undefined;

  const chooseSession = (next: string) => {
    setLapIds(null);
    setParams({ session: next }, { replace: true });
  };
  const chooseTrack = (next: string) => {
    setLapIds(null);
    setParams(editing ? { session: eventId, track: next, test: editing.id } : { session: eventId, track: next }, { replace: true });
  };
  const openTest = (test: AeroTest) => {
    setDraft(draftFromInputs(test.inputs));
    setLapIds(test.lap_ids);
    setParams({ session: test.external_event_id, track: test.track_id, test: test.id });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const stopEditing = () => setParams({ session: eventId, ...(trackId ? { track: trackId } : {}) });

  const save = async (setup: AeroSetup) => {
    try {
      if (editing) {
        await updateTest.mutateAsync({ testId: editing.id, payload: { ...setup, ...inputs, lap_ids: lapIds } });
        toast({ title: t("save.updated"), tone: "success" });
      } else {
        const created = await createTest.mutateAsync({
          ...setup,
          ...inputs,
          external_event_id: eventId,
          track_id: result?.track_id ?? trackId,
          lap_ids: lapIds,
        });
        toast({ title: t("save.saved"), tone: "success" });
        setParams({ session: eventId, track: created.track_id, test: created.id }, { replace: true });
      }
      setSaveOpen(false);
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
    }
  };

  const loading = sessions.isLoading || activities.isLoading || tests.isLoading;
  const nothingYet = !loading && candidates.length === 0 && (tests.data ?? []).length === 0 && !params.get("session");
  const fit = result?.fit ?? null;

  return (
    <>
      <PageHeader title={t("page.title")} description={t("page.description")} />

      {loading && <SkeletonGroup lines={6} />}
      {(sessions.isError || activities.isError) && <p role="alert">{t("common:loadError")}</p>}
      {nothingYet && (
        <EmptyState
          icon={<Wind aria-hidden />}
          title={t("pick.noSessions")}
          description={t("pick.noSessionsHint")}
          action={<ButtonLink to="/import">{t("pick.toImport")}</ButtonLink>}
        />
      )}

      {!loading && !nothingYet && (
        <div className="aero-lab">
          <Card className="aero-lab__pick">
            <div className="aero-lab__pick-row">
              <Select label={t("pick.session")} value={eventId} onChange={(e) => chooseSession(e.target.value)}>
                {eventId !== "" && !candidates.some((s) => s.external_event_id === eventId) && (
                  <option value={eventId}>{result?.event_name ?? eventId}</option>
                )}
                {candidates.map((s) => (
                  <option key={s.external_event_id} value={s.external_event_id}>
                    {fmt.date(s.event_date)} — {s.event_name}
                  </option>
                ))}
              </Select>
              {result && result.tracks.length > 1 && (
                <Select label={t("pick.track")} value={result.track_id} onChange={(e) => chooseTrack(e.target.value)}>
                  {result.tracks.map((track) => (
                    <option key={track.track_id} value={track.track_id}>
                      {track.track_name} ({t("pick.laps", { count: track.lap_count })})
                    </option>
                  ))}
                </Select>
              )}
              <div className="aero-lab__pick-actions">
                {editing && (
                  <Button variant="ghost" onClick={stopEditing}>
                    {t("save.newEstimate")}
                  </Button>
                )}
                <Button disabled={!result || invalid.length > 0} onClick={() => setSaveOpen(true)}>
                  {editing ? t("save.update") : t("save.button")}
                </Button>
              </div>
            </div>
            {editing && <p className="ui-card__hint">{t("save.editing", { label: editing.label })}</p>}
          </Card>

          {estimate.isError && <p role="alert">{errorMessage(estimate.error)}</p>}
          {eventId !== "" && !result && estimate.isFetching && <SkeletonGroup lines={4} />}

          {result && (
            <>
              {result.problem && (
                <Card className="aero-lab__problem">
                  <p role="status">{t(`problems.${result.problem}`)}</p>
                  {(result.problem === "no_track_length" || result.problem === "no_power") && (
                    <Link to={`/sessions/${encodeURIComponent(result.external_event_id)}`}>{t("pick.openSession")}</Link>
                  )}
                </Card>
              )}

              {fit && (
                <div className="aero-lab__stats">
                  <StatTile
                    label={t("stats.cda")}
                    value={fmt.number(fit.cda_m2, 3, 3)}
                    unit="m²"
                    tone="accent"
                    size="lg"
                    hint={fit.cda_se_m2 !== null ? t("stats.se", { value: fmt.number(fit.cda_se_m2, 3, 3) }) : undefined}
                  />
                  <StatTile label={t("stats.crr")} value={fmt.number(fit.crr, 4, 4)} hint={t(`stats.crrSource.${fit.crr_source}`)} />
                  <StatTile
                    label={t("stats.rSquared")}
                    value={fit.r_squared === null ? "—" : fmt.number(fit.r_squared, 3, 3)}
                    hint={fit.r_squared === null ? t("stats.rSquaredNone") : undefined}
                  />
                  <StatTile label={t("stats.laps")} value={fit.laps_used} />
                  <StatTile label={t("stats.speed")} value={fmt.number(fit.speed_ms * 3.6, 1, 1)} unit="km/h" />
                  <StatTile label={t("stats.power")} value={fmt.number(fit.power_w, 0)} unit="W" />
                </div>
              )}

              <div className="aero-lab__body">
                <div className="aero-lab__main">
                  {result.points.length > 0 && (
                    <Card title={t("chart.title")}>
                      <AeroScatter points={result.points} fit={fit} conditions={result.conditions} />
                    </Card>
                  )}
                  {result.points.length > 0 && (
                    <Card
                      title={t("laps.title")}
                      actions={
                        lapIds !== null ? (
                          <Button variant="ghost" size="sm" onClick={() => setLapIds(null)}>
                            {t("laps.reset")}
                          </Button>
                        ) : undefined
                      }
                    >
                      <AeroLapTable
                        points={result.points}
                        manual={lapIds !== null}
                        onToggle={(lapId) => setLapIds(toggleLap(result.points, lapIds, lapId))}
                      />
                    </Card>
                  )}
                </div>
                <Card title={t("inputs.title")} className="aero-lab__side">
                  <p className="ui-card__hint">{t("inputs.hint")}</p>
                  <AeroInputsForm
                    draft={draft}
                    invalid={invalid}
                    conditions={result.conditions}
                    crrUsed={fit?.crr ?? null}
                    onChange={(key, value) => setDraft((current) => ({ ...current, [key]: value }))}
                  />
                </Card>
              </div>
            </>
          )}

          {tests.data && (
            <AeroTestsCard athleteId={athleteId} tests={tests.data} editingId={editing?.id ?? null} onOpen={openTest} />
          )}
        </div>
      )}

      <SaveTestDialog
        key={`${editing?.id ?? "new"}-${saveOpen}`}
        open={saveOpen}
        onOpenChange={setSaveOpen}
        initial={editing}
        saving={createTest.isPending || updateTest.isPending}
        onSave={save}
      />
    </>
  );
}
