import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button, Dialog, Input, Textarea } from "../../components/ui";
import type { AeroSetup } from "./types";

const TEXT_FIELDS = ["position", "helmet", "skinsuit", "bike"] as const;

const blankToNull = (value: string) => (value.trim() === "" ? null : value.trim());

/** Names the setup of an aero test. Mount it with a `key` to reset it to `initial`. */
export function SaveTestDialog({
  open,
  onOpenChange,
  initial,
  saving,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial: AeroSetup | null;
  saving: boolean;
  onSave: (setup: AeroSetup) => void;
}) {
  const { t } = useTranslation("aero");
  const [label, setLabel] = useState(initial?.label ?? "");
  const [fields, setFields] = useState<Record<(typeof TEXT_FIELDS)[number], string>>({
    position: initial?.position ?? "",
    helmet: initial?.helmet ?? "",
    skinsuit: initial?.skinsuit ?? "",
    bike: initial?.bike ?? "",
  });
  const [notes, setNotes] = useState(initial?.notes ?? "");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (label.trim() === "") return;
    onSave({
      label: label.trim(),
      position: blankToNull(fields.position),
      helmet: blankToNull(fields.helmet),
      skinsuit: blankToNull(fields.skinsuit),
      bike: blankToNull(fields.bike),
      notes: blankToNull(notes),
    });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("save.title")}
      description={t("save.description")}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t("save.cancel")}
          </Button>
          <Button type="submit" form="aero-save-form" loading={saving} disabled={label.trim() === ""}>
            {t("save.confirm")}
          </Button>
        </>
      }
    >
      <form id="aero-save-form" className="aero-lab__save-form" onSubmit={submit}>
        <Input
          label={t("save.label")}
          placeholder={t("save.labelPlaceholder")}
          value={label}
          maxLength={100}
          required
          autoFocus
          onChange={(e) => setLabel(e.target.value)}
        />
        <div className="aero-lab__save-grid">
          {TEXT_FIELDS.map((field) => (
            <Input
              key={field}
              label={t(`save.${field}`)}
              value={fields[field]}
              maxLength={100}
              onChange={(e) => setFields((current) => ({ ...current, [field]: e.target.value }))}
            />
          ))}
        </div>
        <Textarea label={t("save.notes")} value={notes} maxLength={5000} rows={3} onChange={(e) => setNotes(e.target.value)} />
      </form>
    </Dialog>
  );
}
