import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Card, Checkbox, useToast } from "../../components/ui";
import type { Athlete } from "../athletes/types";
import { useUpdateAthlete } from "../athletes/useAthlete";
import { SPORT_DEFS, SPORTS, type Sport } from "../sports/registry";
import { useAthleteSports } from "../sports/useMySports";

/** "My sports": which sport-specific pages and cards the app shows. */
export function SportsSettings({ athlete }: { athlete: Athlete }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const update = useUpdateAthlete(athlete.id);
  const current = useAthleteSports(athlete);
  const [picked, setPicked] = useState<Set<Sport> | null>(null);
  const selected = picked ?? current.sports;

  const dirty = picked !== null && (!current.chosen || picked.size !== current.sports.size || [...picked].some((s) => !current.sports.has(s)));

  function toggle(sport: Sport) {
    const next = new Set(selected);
    if (next.has(sport)) next.delete(sport);
    else next.add(sport);
    setPicked(next);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await update.mutateAsync({ sports: SPORTS.filter((sport) => selected.has(sport)) });
      setPicked(null);
      toast({ title: t("sports.saved"), tone: "success" });
    } catch {
      // surfaced via update.error below
    }
  }

  return (
    <Card title={t("sports.title")} as="section">
      <form className="settings-form" onSubmit={handleSubmit}>
        <p className="settings-section__description">
          {t("sports.description")} {!current.chosen && t("sports.guessed")}
        </p>
        <div className="settings-sports">
          {SPORTS.map((sport) => {
            const Icon = SPORT_DEFS[sport].icon;
            return (
              <Checkbox
                key={sport}
                checked={selected.has(sport)}
                onChange={() => toggle(sport)}
                label={
                  <span className="settings-sports__label">
                    <Icon aria-hidden />
                    {t(`sports.names.${sport}`)}
                  </span>
                }
              />
            );
          })}
        </div>
        {update.error && <p role="alert" className="settings-form__error">{errorMessage(update.error)}</p>}
        <div className="settings-form__actions">
          <Button type="submit" loading={update.isPending} disabled={selected.size === 0 || (!dirty && current.chosen)}>
            {update.isPending ? tc("saving") : tc("save")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
