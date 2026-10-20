import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Dialog, Input, Select, useToast } from "../../components/ui";
import { localIsoDate } from "../../i18n/format";
import type { Sex } from "../athletes/types";
import { useCreateManagedAthlete } from "./useClubs";

/** A profile with no login (a junior, say) that the club's admins run. */
export function ManagedAthleteDialog({
  clubId,
  open,
  onOpenChange,
}: {
  clubId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation("club");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const create = useCreateManagedAthlete(clubId);
  const [name, setName] = useState("");
  const [birthdate, setBirthdate] = useState("");
  const [sex, setSex] = useState<Sex | "">("");
  const [showErrors, setShowErrors] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (name.trim() === "") {
      setShowErrors(true);
      return;
    }
    try {
      await create.mutateAsync({ display_name: name.trim(), birthdate: birthdate || null, sex: sex || null });
      toast({ title: t("roster.added"), tone: "success" });
      setName("");
      setBirthdate("");
      setSex("");
      setShowErrors(false);
      onOpenChange(false);
    } catch {
      // shown in the form
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("roster.addTitle")}
      description={t("roster.addDescription")}
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="managed-athlete-form" loading={create.isPending}>
            {t("roster.addSubmit")}
          </Button>
        </>
      }
    >
      <form id="managed-athlete-form" className="club-form" onSubmit={handleSubmit} noValidate>
        <Input
          label={t("roster.name")}
          value={name}
          maxLength={255}
          autoFocus
          error={showErrors && name.trim() === "" ? t("roster.nameRequired") : undefined}
          onChange={(e) => setName(e.target.value)}
        />
        <div className="club-form__row">
          <Input label={t("roster.birthdate")} type="date" value={birthdate} max={localIsoDate()} onChange={(e) => setBirthdate(e.target.value)} />
          <Select label={t("roster.sex")} value={sex} onChange={(e) => setSex(e.target.value as Sex | "")}>
            <option value="">{tc("none")}</option>
            <option value="female">{t("roster.sexes.female")}</option>
            <option value="male">{t("roster.sexes.male")}</option>
          </Select>
        </div>
        {create.isError && <p role="alert">{errorMessage(create.error)}</p>}
      </form>
    </Dialog>
  );
}
