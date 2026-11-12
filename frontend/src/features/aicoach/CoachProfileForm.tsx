import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Card, Checkbox, Dialog, Input, Select, SkeletonGroup, Textarea, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { useLanguage } from "../../i18n/useLanguage";
import { WEEKDAYS, weekdayName } from "./proposalText";
import type { CoachProfile, CoachSettings } from "./types";
import { useCoachProfile, useConsent, useSaveCoachProfile } from "./useAiCoach";

type Draft = Record<
  "goal" | "goal_date" | "hours_per_week" | "max_weekday_minutes" | "max_weekend_minutes" | "experience" | "injuries" | "gym_details" | "other",
  string
> & {
  available_days: number[];
  track_days: number[];
  gym: boolean;
  indoor_trainer: boolean;
  power_meter: boolean;
};

const str = (value: string | number | null | undefined) => (value == null ? "" : String(value));
const num = (value: string) => (value.trim() === "" || Number.isNaN(Number(value.replace(",", "."))) ? null : Number(value.replace(",", ".")));
const txt = (value: string) => value.trim() || null;

function toDraft(answers: CoachProfile): Draft {
  return {
    goal: str(answers.goal),
    goal_date: str(answers.goal_date),
    hours_per_week: str(answers.hours_per_week),
    max_weekday_minutes: str(answers.max_weekday_minutes),
    max_weekend_minutes: str(answers.max_weekend_minutes),
    experience: str(answers.experience),
    injuries: str(answers.injuries),
    gym_details: str(answers.gym_details),
    other: str(answers.other),
    available_days: answers.available_days ?? [],
    track_days: answers.track_days ?? [],
    gym: !!answers.gym,
    indoor_trainer: !!answers.indoor_trainer,
    power_meter: !!answers.power_meter,
  };
}

function fromDraft(draft: Draft): CoachProfile {
  return {
    goal: txt(draft.goal),
    goal_date: txt(draft.goal_date),
    hours_per_week: num(draft.hours_per_week),
    max_weekday_minutes: num(draft.max_weekday_minutes),
    max_weekend_minutes: num(draft.max_weekend_minutes),
    experience: txt(draft.experience),
    injuries: txt(draft.injuries),
    gym: draft.gym,
    gym_details: txt(draft.gym_details),
    indoor_trainer: draft.indoor_trainer,
    power_meter: draft.power_meter,
    other: txt(draft.other),
    available_days: draft.available_days,
    track_days: draft.track_days,
  };
}

function DayPicker({ legend, value, onChange }: { legend: string; value: number[]; onChange: (days: number[]) => void }) {
  const { language } = useLanguage();
  return (
    <fieldset className="ai-days">
      <legend>{legend}</legend>
      {WEEKDAYS.map((day) => (
        <Checkbox
          key={day}
          label={weekdayName(day, language)}
          checked={value.includes(day)}
          onChange={(event) => onChange(event.target.checked ? [...value, day].sort() : value.filter((d) => d !== day))}
        />
      ))}
    </fieldset>
  );
}

/** What the AI coach knows about the athlete (it fills it during the interview), the report schedule and consent. */
export function CoachProfileForm({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation(["aicoach", "common"]);
  const fmt = useFormat();
  const { language } = useLanguage();
  const { toast } = useToast();
  const profile = useCoachProfile(athleteId);
  const save = useSaveCoachProfile(athleteId);
  const consent = useConsent(athleteId);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [settings, setSettings] = useState<CoachSettings | null>(null);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [deleteHistory, setDeleteHistory] = useState(false);

  useEffect(() => {
    if (profile.data) {
      setDraft(toDraft(profile.data.answers));
      setSettings(profile.data.settings);
    }
  }, [profile.data]);

  if (profile.isLoading || !draft || !settings) return <SkeletonGroup lines={6} />;
  const set = <K extends keyof Draft>(field: K, value: Draft[K]) => setDraft({ ...draft, [field]: value });
  const program = profile.data?.program;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate(
      { answers: fromDraft(draft!), settings: settings! },
      { onSuccess: () => toast({ title: t("profile.saved"), tone: "success" }) },
    );
  }

  return (
    <div className="ai-stack">
      {program && (
        <Card as="section" title={t("profile.program")}>
          {program.goal && <p>{program.goal}</p>}
          {program.outline && program.outline.length > 0 && (
            <ol className="ai-outline">
              {program.outline.map((week) => (
                <li key={week.week_start}>
                  <strong>{t("proposal.weekOf", { date: fmt.date(week.week_start, "dayMonth") })}</strong> · {week.focus}
                  {week.hours != null && <> · {t("proposal.hours", { value: fmt.number(week.hours) })}</>}
                </li>
              ))}
            </ol>
          )}
        </Card>
      )}

      <form onSubmit={onSubmit} className="ai-stack">
        <Card as="section" title={t("profile.title")}>
          <p className="ai-muted">{t("profile.hint")}</p>
          <div className="ai-form-grid">
            <Textarea label={t("profile.goal")} value={draft.goal} onChange={(e) => set("goal", e.target.value)} rows={2} maxLength={500} />
            <Input label={t("profile.goalDate")} type="date" value={draft.goal_date} onChange={(e) => set("goal_date", e.target.value)} />
            <Input
              label={t("profile.hours")}
              inputMode="decimal"
              value={draft.hours_per_week}
              onChange={(e) => set("hours_per_week", e.target.value)}
            />
            <Input
              label={t("profile.weekdayMinutes")}
              inputMode="numeric"
              value={draft.max_weekday_minutes}
              onChange={(e) => set("max_weekday_minutes", e.target.value)}
            />
            <Input
              label={t("profile.weekendMinutes")}
              inputMode="numeric"
              value={draft.max_weekend_minutes}
              onChange={(e) => set("max_weekend_minutes", e.target.value)}
            />
          </div>
          <DayPicker legend={t("profile.availableDays")} value={draft.available_days} onChange={(days) => set("available_days", days)} />
          <DayPicker legend={t("profile.trackDays")} value={draft.track_days} onChange={(days) => set("track_days", days)} />
          <div className="ai-form-grid">
            <Textarea label={t("profile.injuries")} value={draft.injuries} onChange={(e) => set("injuries", e.target.value)} rows={2} maxLength={1000} />
            <Textarea label={t("profile.experience")} value={draft.experience} onChange={(e) => set("experience", e.target.value)} rows={2} maxLength={500} />
          </div>
          <div className="ai-checks">
            <Checkbox label={t("profile.gym")} checked={draft.gym} onChange={(e) => set("gym", e.target.checked)} />
            <Checkbox label={t("profile.indoor")} checked={draft.indoor_trainer} onChange={(e) => set("indoor_trainer", e.target.checked)} />
            <Checkbox label={t("profile.powerMeter")} checked={draft.power_meter} onChange={(e) => set("power_meter", e.target.checked)} />
          </div>
          {draft.gym && (
            <Input label={t("profile.gymDetails")} value={draft.gym_details} onChange={(e) => set("gym_details", e.target.value)} maxLength={500} />
          )}
          <Textarea label={t("profile.other")} value={draft.other} onChange={(e) => set("other", e.target.value)} rows={2} maxLength={1000} />
        </Card>

        <Card as="section" title={t("profile.reports")}>
          <Checkbox
            label={t("profile.weeklyReports")}
            checked={settings.weekly_reports}
            onChange={(e) => setSettings({ ...settings, weekly_reports: e.target.checked })}
          />
          <div className="ai-form-grid">
            <Select
              label={t("profile.reportDay")}
              value={settings.report_weekday}
              disabled={!settings.weekly_reports}
              onChange={(e) => setSettings({ ...settings, report_weekday: Number(e.target.value) })}
            >
              {WEEKDAYS.map((day) => (
                <option key={day} value={day}>
                  {weekdayName(day, language, "long")}
                </option>
              ))}
            </Select>
            <Select
              label={t("profile.reportHour")}
              value={settings.report_hour}
              disabled={!settings.weekly_reports}
              onChange={(e) => setSettings({ ...settings, report_hour: Number(e.target.value) })}
            >
              {Array.from({ length: 24 }, (_, hour) => (
                <option key={hour} value={hour}>
                  {`${String(hour).padStart(2, "0")}:00`}
                </option>
              ))}
            </Select>
          </div>
        </Card>

        <div className="ai-row">
          <Button type="submit" loading={save.isPending}>
            {t("profile.save")}
          </Button>
          {save.isError && <span className="ai-error">{errorMessage(save.error)}</span>}
        </div>
      </form>

      <Card as="section" title={t("profile.consentTitle")}>
        <p className="ai-muted">{t("profile.consentHint")}</p>
        <Button variant="danger" onClick={() => setWithdrawOpen(true)}>
          {t("profile.withdraw")}
        </Button>
      </Card>
      <Dialog
        open={withdrawOpen}
        onOpenChange={setWithdrawOpen}
        title={t("profile.withdrawTitle")}
        description={t("profile.withdrawHint")}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setWithdrawOpen(false)} disabled={consent.isPending}>
              {t("common:cancel")}
            </Button>
            <Button
              variant="danger"
              loading={consent.isPending}
              onClick={() => consent.mutate({ give: false, deleteHistory }, { onSuccess: () => setWithdrawOpen(false) })}
            >
              {t("profile.withdraw")}
            </Button>
          </>
        }
      >
        <Checkbox label={t("profile.deleteHistory")} checked={deleteHistory} onChange={(e) => setDeleteHistory(e.target.checked)} />
      </Dialog>
    </div>
  );
}
