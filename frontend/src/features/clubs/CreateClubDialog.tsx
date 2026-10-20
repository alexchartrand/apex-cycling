import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Button, Dialog, Input, useToast } from "../../components/ui";
import { browserTimeZone, isValidTimeZone } from "./timeZone";
import { useCreateClub } from "./useClubs";

export function CreateClubDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation("club");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const navigate = useNavigate();
  const create = useCreateClub();
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState(browserTimeZone);
  const [showErrors, setShowErrors] = useState(false);
  const nameOk = name.trim().length > 0;
  const zoneOk = isValidTimeZone(timezone);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!nameOk || !zoneOk) {
      setShowErrors(true);
      return;
    }
    try {
      const club = await create.mutateAsync({ name: name.trim(), timezone: timezone.trim() });
      toast({ title: t("create.created"), tone: "success" });
      onOpenChange(false);
      navigate(`/club/${club.id}`);
    } catch {
      // shown in the form
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("create.title")}
      description={t("create.description")}
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="create-club-form" loading={create.isPending}>
            {t("create.submit")}
          </Button>
        </>
      }
    >
      <form id="create-club-form" className="club-form" onSubmit={handleSubmit} noValidate>
        <Input
          label={t("create.name")}
          value={name}
          maxLength={255}
          autoFocus
          error={showErrors && !nameOk ? t("create.nameRequired") : undefined}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          label={t("create.timezone")}
          value={timezone}
          list="club-timezones"
          hint={t("create.timezoneHint")}
          error={showErrors && !zoneOk ? t("create.timezoneInvalid") : undefined}
          onChange={(e) => setTimezone(e.target.value)}
        />
        <datalist id="club-timezones">
          {(Intl.supportedValuesOf?.("timeZone") ?? []).map((zone) => (
            <option key={zone} value={zone} />
          ))}
        </datalist>
        {create.isError && <p role="alert">{errorMessage(create.error, { 429: t("create.tooMany") })}</p>}
      </form>
    </Dialog>
  );
}
