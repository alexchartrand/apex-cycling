import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Card, Input, useToast } from "../../components/ui";
import type { Club } from "./types";
import { browserTimeZone, isValidTimeZone } from "./timeZone";
import { useUpdateClub } from "./useClubs";

export function ClubSettingsPanel({ club }: { club: Club }) {
  const { t } = useTranslation("club");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const update = useUpdateClub(club.id);
  const [name, setName] = useState(club.name);
  const [timezone, setTimezone] = useState(club.timezone);
  const zoneOk = isValidTimeZone(timezone);
  const dirty = name.trim() !== club.name || timezone.trim() !== club.timezone;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!dirty || name.trim() === "" || !zoneOk) return;
    try {
      await update.mutateAsync({ name: name.trim(), timezone: timezone.trim() });
      toast({ title: t("settings.saved"), tone: "success" });
    } catch {
      // shown below
    }
  }

  return (
    <Card as="section" title={t("tabs.settings")}>
      <form className="club-form club-form--narrow" onSubmit={handleSubmit} noValidate>
        <Input label={t("create.name")} value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
        <Input
          label={t("create.timezone")}
          value={timezone}
          list="club-timezones"
          hint={t("settings.timezoneHint", { zone: browserTimeZone() })}
          error={zoneOk ? undefined : t("create.timezoneInvalid")}
          onChange={(e) => setTimezone(e.target.value)}
        />
        <datalist id="club-timezones">
          {(Intl.supportedValuesOf?.("timeZone") ?? []).map((zone) => (
            <option key={zone} value={zone} />
          ))}
        </datalist>
        <p className="club-muted">{t("settings.slug", { slug: club.slug })}</p>
        {update.isError && <p role="alert">{errorMessage(update.error)}</p>}
        <div className="club-form__actions">
          <Button type="submit" loading={update.isPending} disabled={!dirty || name.trim() === "" || !zoneOk}>
            {tc("save")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
