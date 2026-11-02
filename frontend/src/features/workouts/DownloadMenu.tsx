import { Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Menu, MenuItem, useToast } from "../../components/ui";
import { EXPORT_FORMATS, type ExportFormat } from "./types";

/** "Download" → .fit / .zwo / .erg / .mrc; `download` fetches and saves the file. */
export function DownloadMenu({ download }: { download: (format: ExportFormat) => Promise<void> }) {
  const { t } = useTranslation("workouts");
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
    </Menu>
  );
}
