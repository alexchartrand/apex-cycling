import { Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Menu, MenuItem, MenuLabel, MenuSeparator, useToast } from "../../components/ui";
import { EXPORT_FORMATS, type ExportFormat } from "./types";
import { WORKOUT_CARD_SIZES, type WorkoutCardSize } from "./workoutCard";

/**
 * "Download" → .fit / .zwo / .erg / .mrc; `download` fetches and saves the file.
 * With `card`, also the workout as a picture (lock screen or stem strip), drawn here.
 */
export function DownloadMenu({
  download,
  card,
}: {
  download: (format: ExportFormat) => Promise<void>;
  card?: (size: WorkoutCardSize) => Promise<"shared" | "downloaded" | "cancelled">;
}) {
  const { t } = useTranslation("workouts");
  const { t: ts } = useTranslation("share");
  const { toast } = useToast();
  const [pending, setPending] = useState(false);

  async function run(format: ExportFormat) {
    setPending(true);
    try {
      await download(format);
    } catch (error) {
      toast({ title: errorMessage(error, { 409: t("download.needsFtp") }), tone: "error" });
    } finally {
      setPending(false);
    }
  }

  async function runCard(size: WorkoutCardSize) {
    if (!card) return;
    setPending(true);
    try {
      const outcome = await card(size);
      if (outcome === "downloaded") toast({ title: ts("saved"), description: t(`card.savedHint.${size}`), tone: "success" });
    } catch {
      toast({ title: ts("failed"), tone: "error" });
    } finally {
      setPending(false);
    }
  }

  return (
    <Menu
      trigger={
        <Button variant="secondary" icon={<Download aria-hidden />} loading={pending}>
          {t("download.button")}
        </Button>
      }
    >
      {EXPORT_FORMATS.map((format) => (
        <MenuItem key={format} onSelect={() => void run(format)}>
          {t(`download.formats.${format}`)}
        </MenuItem>
      ))}
      {card && (
        <>
          <MenuSeparator />
          <MenuLabel>{t("card.title")}</MenuLabel>
          {WORKOUT_CARD_SIZES.map((size) => (
            <MenuItem key={size} onSelect={() => void runCard(size)}>
              {t(`card.sizes.${size}`)}
            </MenuItem>
          ))}
        </>
      )}
    </Menu>
  );
}
