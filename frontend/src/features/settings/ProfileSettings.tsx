import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, Input, Select, useToast } from "../../components/ui";
import { localIsoDate } from "../../i18n/format";
import { ageCategoryLabel } from "../athletes/ageCategory";
import type { Athlete, Sex } from "../athletes/types";
import { useUpdateAthlete } from "../athletes/useAthlete";
import type { User } from "../auth/types";

/** The age turned this calendar year, which cycling categories go by (the category code itself comes from the backend). */
function raceAge(birthdate: string): number {
  return new Date().getFullYear() - Number(birthdate.slice(0, 4));
}

export function ProfileSettings({ athlete, user }: { athlete: Athlete; user: User }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const update = useUpdateAthlete(athlete.id);

  const [displayName, setDisplayName] = useState(athlete.display_name);
  const [birthdate, setBirthdate] = useState(athlete.birthdate ?? "");
  const [sex, setSex] = useState<Sex | "">(athlete.sex ?? "");
  const [height, setHeight] = useState(athlete.height_cm?.toString() ?? "");

  const dirty =
    displayName !== athlete.display_name ||
    birthdate !== (athlete.birthdate ?? "") ||
    sex !== (athlete.sex ?? "") ||
    height !== (athlete.height_cm?.toString() ?? "");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await update.mutateAsync({
        display_name: displayName.trim(),
        birthdate: birthdate || null,
        sex: sex || null,
        height_cm: height ? Number(height) : null,
      });
      toast({ title: t("profile.saved"), tone: "success" });
    } catch {
      // surfaced via update.error below
    }
  }

  return (
    <Card title={t("profile.title")} as="section">
      <form className="settings-form" onSubmit={handleSubmit}>
        <div className="settings-form__grid">
          <Input
            label={t("profile.name")}
            autoComplete="name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={255}
            required
          />
          <Input label={t("profile.email")} type="email" value={user.email} hint={t("profile.emailHint")} readOnly disabled />
          <Input
            label={t("profile.birthdate")}
            type="date"
            value={birthdate}
            max={localIsoDate()}
            min="1900-01-01"
            onChange={(e) => setBirthdate(e.target.value)}
            hint={t("profile.birthdateHint")}
          />
          <Select label={t("profile.sex")} value={sex} onChange={(e) => setSex(e.target.value as Sex | "")} hint={t("profile.sexHint")}>
            <option value="">{t("profile.sexOptions.unset")}</option>
            <option value="female">{t("profile.sexOptions.female")}</option>
            <option value="male">{t("profile.sexOptions.male")}</option>
          </Select>
          <Input
            label={t("profile.height")}
            type="number"
            inputMode="decimal"
            min={51}
            max={259}
            step={0.5}
            suffix={tc("units.cm")}
            value={height}
            onChange={(e) => setHeight(e.target.value)}
          />
        </div>

        <div className="settings-category">
          <span className="settings-category__label">{t("profile.category")}</span>
          {athlete.category && athlete.birthdate ? (
            <span className="settings-category__value">
              <Badge tone="accent">{ageCategoryLabel(athlete.category, tc)}</Badge>
              <span className="settings-category__hint">{t("profile.raceAge", { age: raceAge(athlete.birthdate) })}</span>
            </span>
          ) : (
            <span className="settings-category__hint">{t("profile.categoryNone")}</span>
          )}
        </div>

        {update.error && <p role="alert" className="settings-form__error">{errorMessage(update.error)}</p>}
        <div className="settings-form__actions">
          <Button type="submit" loading={update.isPending} disabled={!dirty || displayName.trim() === ""}>
            {update.isPending ? tc("saving") : tc("save")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
