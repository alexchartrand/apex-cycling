import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Card, ConfirmDialog, Dialog, EmptyState, IconButton, Input, SkeletonGroup, Textarea, Tooltip, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { gearName, parseNumber } from "./gear";
import { RolloutPresetSelect } from "./RolloutPresetSelect";
import { TireSelect } from "./TireSelect";
import { DEFAULT_ROLLOUT_MM, GEAR_BOUNDS, type Bike, type Gear } from "./types";
import { useBikes, useDeleteBike, useDeleteGear, useSaveBike, useSaveGear } from "./useEquipment";
import "./EquipmentPanel.css";

export function EquipmentPanel({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("equipment");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const bikes = useBikes(athleteId);
  const removeBike = useDeleteBike(athleteId);
  const removeGear = useDeleteGear(athleteId);
  const [editingBike, setEditingBike] = useState<Bike | "new" | null>(null);
  const [editingGear, setEditingGear] = useState<{ bike: Bike; gear: Gear | null } | null>(null);
  const [deletingBike, setDeletingBike] = useState<Bike | null>(null);
  const [deletingGear, setDeletingGear] = useState<Gear | null>(null);

  return (
    <>
      <Card
        as="section"
        actions={
          <Button size="sm" icon={<Plus aria-hidden />} onClick={() => setEditingBike("new")}>
            {t("addBike")}
          </Button>
        }
      >
        <p className="equipment__description">{t("description")}</p>
        {bikes.isLoading && <SkeletonGroup lines={3} />}
        {bikes.isError && <p role="alert">{tc("loadError")}</p>}
        {bikes.data?.length === 0 && <EmptyState compact title={t("empty")} description={t("emptyHint")} />}
      </Card>

      {bikes.data?.map((bike) => (
        <Card
          key={bike.id}
          as="article"
          title={bike.name}
          eyebrow={bike.weight_kg != null ? `${fmt.number(bike.weight_kg, 1, 1)} ${tc("units.kg")}` : undefined}
          actions={
            <>
              <Tooltip content={t("editBike", { name: bike.name })}>
                <IconButton aria-label={t("editBike", { name: bike.name })} variant="ghost" onClick={() => setEditingBike(bike)}>
                  <Pencil aria-hidden />
                </IconButton>
              </Tooltip>
              <Tooltip content={t("deleteBike", { name: bike.name })}>
                <IconButton aria-label={t("deleteBike", { name: bike.name })} variant="ghost" onClick={() => setDeletingBike(bike)}>
                  <Trash2 aria-hidden />
                </IconButton>
              </Tooltip>
            </>
          }
        >
          {bike.notes && <p className="equipment__notes">{bike.notes}</p>}
          {bike.gears.length === 0 ? (
            <p className="equipment__none">{t("gear.none")}</p>
          ) : (
            <ul className="equipment__gears">
              {bike.gears.map((gear) => (
                <li key={gear.id} className="equipment__gear">
                  <span className="equipment__gear-name">{gearName(gear)}</span>
                  <span className="equipment__gear-detail">
                    {t("gear.development", { value: fmt.number(gear.development_m, 2, 2) })} ·{" "}
                    {t("gear.gearInches", { value: fmt.number(gear.gear_inches, 1, 1) })}
                    {gear.tire ? ` · ${gear.tire}` : ""}
                    {gear.crr != null ? ` · ${t("gear.crrValue", { value: fmt.number(gear.crr, 6, 3) })}` : ""}
                  </span>
                  <span className="equipment__gear-actions">
                    <Tooltip content={t("gear.edit", { name: gearName(gear) })}>
                      <IconButton
                        size="sm"
                        aria-label={t("gear.edit", { name: gearName(gear) })}
                        onClick={() => setEditingGear({ bike, gear })}
                      >
                        <Pencil aria-hidden />
                      </IconButton>
                    </Tooltip>
                    <Tooltip content={t("gear.delete", { name: gearName(gear) })}>
                      <IconButton size="sm" aria-label={t("gear.delete", { name: gearName(gear) })} onClick={() => setDeletingGear(gear)}>
                        <Trash2 aria-hidden />
                      </IconButton>
                    </Tooltip>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="equipment__add">
            <Button size="sm" variant="secondary" icon={<Plus aria-hidden />} onClick={() => setEditingGear({ bike, gear: null })}>
              {t("gear.add")}
            </Button>
          </div>
        </Card>
      ))}

      {editingBike && (
        <BikeDialog
          key={editingBike === "new" ? "new" : editingBike.id}
          athleteId={athleteId}
          bike={editingBike === "new" ? null : editingBike}
          onClose={() => setEditingBike(null)}
        />
      )}
      {editingGear && (
        <GearDialog
          key={editingGear.gear?.id ?? `new-${editingGear.bike.id}`}
          athleteId={athleteId}
          bike={editingGear.bike}
          gear={editingGear.gear}
          onClose={() => setEditingGear(null)}
        />
      )}
      <ConfirmDialog
        open={deletingBike != null}
        onOpenChange={(open) => !open && setDeletingBike(null)}
        title={t("bike.deleteTitle")}
        description={t("bike.deleteBody", { name: deletingBike?.name ?? "" })}
        confirmLabel={tc("delete")}
        cancelLabel={tc("cancel")}
        tone="danger"
        onConfirm={async () => {
          try {
            await removeBike.mutateAsync(deletingBike!.id);
            toast({ title: t("bike.deleted"), tone: "success" });
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
      <ConfirmDialog
        open={deletingGear != null}
        onOpenChange={(open) => !open && setDeletingGear(null)}
        title={t("gear.deleteTitle")}
        description={t("gear.deleteBody", { name: deletingGear ? gearName(deletingGear) : "" })}
        confirmLabel={tc("delete")}
        cancelLabel={tc("cancel")}
        tone="danger"
        onConfirm={async () => {
          try {
            await removeGear.mutateAsync(deletingGear!.id);
            toast({ title: t("gear.deleted"), tone: "success" });
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </>
  );
}

function BikeDialog({ athleteId, bike, onClose }: { athleteId: string; bike: Bike | null; onClose: () => void }) {
  const { t } = useTranslation("equipment");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const save = useSaveBike(athleteId);
  const [name, setName] = useState(bike?.name ?? "");
  const [weight, setWeight] = useState(bike?.weight_kg != null ? String(bike.weight_kg) : "");
  const [notes, setNotes] = useState(bike?.notes ?? "");
  const weightKg = parseNumber(weight);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await save.mutateAsync({
        bikeId: bike?.id,
        payload: { name: name.trim(), weight_kg: weightKg, notes: notes.trim() || null },
      });
      toast({ title: t("bike.saved"), tone: "success" });
      onClose();
    } catch {
      // shown inside the dialog
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={bike ? t("editBike", { name: bike.name }) : t("addBike")}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="bike-form" loading={save.isPending} disabled={name.trim() === ""}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="bike-form" className="equipment__form" onSubmit={handleSubmit}>
        <Input label={t("bike.name")} value={name} maxLength={100} placeholder={t("bike.namePlaceholder")} onChange={(e) => setName(e.target.value)} autoFocus />
        <Input
          label={t("bike.weight")}
          hint={t("bike.weightHint")}
          type="number"
          inputMode="decimal"
          min={GEAR_BOUNDS.bikeKg.min}
          max={GEAR_BOUNDS.bikeKg.max}
          step={0.1}
          suffix={tc("units.kg")}
          value={weight}
          onChange={(e) => setWeight(e.target.value)}
        />
        <Textarea label={t("bike.notes")} value={notes} maxLength={2000} rows={3} onChange={(e) => setNotes(e.target.value)} />
        {save.isError && <p role="alert" className="equipment__error">{errorMessage(save.error)}</p>}
      </form>
    </Dialog>
  );
}

function GearDialog({ athleteId, bike, gear, onClose }: { athleteId: string; bike: Bike; gear: Gear | null; onClose: () => void }) {
  const { t } = useTranslation("equipment");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const save = useSaveGear(athleteId);
  const [chainring, setChainring] = useState(gear ? String(gear.chainring_teeth) : "");
  const [cog, setCog] = useState(gear ? String(gear.cog_teeth) : "");
  const [rollout, setRollout] = useState(String(gear?.rollout_mm ?? DEFAULT_ROLLOUT_MM));
  const [tire, setTire] = useState(gear?.tire ?? "");
  const [crr, setCrr] = useState(gear?.crr != null ? String(gear.crr) : "");
  const values = { chainring_teeth: parseNumber(chainring), cog_teeth: parseNumber(cog), rollout_mm: parseNumber(rollout) };
  const crrValue = parseNumber(crr);
  const valid =
    values.chainring_teeth != null &&
    Number.isInteger(values.chainring_teeth) &&
    values.chainring_teeth >= GEAR_BOUNDS.chainring.min &&
    values.chainring_teeth <= GEAR_BOUNDS.chainring.max &&
    values.cog_teeth != null &&
    Number.isInteger(values.cog_teeth) &&
    values.cog_teeth >= GEAR_BOUNDS.cog.min &&
    values.cog_teeth <= GEAR_BOUNDS.cog.max &&
    values.rollout_mm != null &&
    values.rollout_mm >= GEAR_BOUNDS.rollout.min &&
    values.rollout_mm <= GEAR_BOUNDS.rollout.max &&
    (crr.trim() === "" || (crrValue != null && crrValue >= GEAR_BOUNDS.crr.min && crrValue <= GEAR_BOUNDS.crr.max));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    try {
      await save.mutateAsync({
        bikeId: bike.id,
        gearId: gear?.id,
        payload: {
          chainring_teeth: values.chainring_teeth!,
          cog_teeth: values.cog_teeth!,
          rollout_mm: values.rollout_mm!,
          tire: tire.trim() || null,
          crr: crrValue,
        },
      });
      toast({ title: t("gear.saved"), tone: "success" });
      onClose();
    } catch {
      // shown inside the dialog
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={gear ? t("gear.edit", { name: gearName(gear) }) : `${t("gear.add")} · ${bike.name}`}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="gear-form" loading={save.isPending} disabled={!valid}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="gear-form" className="equipment__form" onSubmit={handleSubmit}>
        <div className="equipment__row">
          <Input
            label={t("gear.chainring")}
            type="number"
            inputMode="numeric"
            min={GEAR_BOUNDS.chainring.min}
            max={GEAR_BOUNDS.chainring.max}
            step={1}
            suffix={t("gear.teeth")}
            value={chainring}
            onChange={(e) => setChainring(e.target.value)}
            autoFocus
          />
          <Input
            label={t("gear.cog")}
            type="number"
            inputMode="numeric"
            min={GEAR_BOUNDS.cog.min}
            max={GEAR_BOUNDS.cog.max}
            step={1}
            suffix={t("gear.teeth")}
            value={cog}
            onChange={(e) => setCog(e.target.value)}
          />
        </div>
        <div className="equipment__row">
          <RolloutPresetSelect rolloutMm={values.rollout_mm} onChange={(mm) => setRollout(String(mm))} />
          <Input
            label={t("gear.rollout")}
            hint={t("gear.rolloutHint")}
            type="number"
            inputMode="decimal"
            min={GEAR_BOUNDS.rollout.min}
            max={GEAR_BOUNDS.rollout.max}
            step={1}
            suffix="mm"
            value={rollout}
            onChange={(e) => setRollout(e.target.value)}
          />
        </div>
        <TireSelect
          name={tire}
          crr={crrValue}
          onChange={(picked) => {
            setTire(picked.label);
            setCrr(String(picked.crr));
          }}
        />
        <div className="equipment__row">
          <Input label={t("gear.tire")} value={tire} maxLength={100} placeholder={t("gear.tirePlaceholder")} onChange={(e) => setTire(e.target.value)} />
          <Input
            label={t("gear.crr")}
            hint={t("gear.crrHint")}
            type="number"
            inputMode="decimal"
            min={GEAR_BOUNDS.crr.min}
            max={GEAR_BOUNDS.crr.max}
            step="any"
            placeholder="0.004"
            value={crr}
            onChange={(e) => setCrr(e.target.value)}
          />
        </div>
        {save.isError && <p role="alert" className="equipment__error">{errorMessage(save.error)}</p>}
      </form>
    </Dialog>
  );
}
