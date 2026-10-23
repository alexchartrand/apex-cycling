import { Share2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { IconButton, Tooltip, useToast } from "../../components/ui";
import { renderShareCard, shareImage } from "./renderShareCard";
import { shareFileName, type ShareCardModel } from "./shareCard";

/** Builds the card on click (so nothing is drawn for cards nobody shares) and shares or saves it. */
export function ShareButton({ buildModel, label }: { buildModel: () => ShareCardModel; label?: string }) {
  const { t } = useTranslation("share");
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const text = label ?? t("share");

  async function handleClick() {
    setBusy(true);
    try {
      const model = buildModel();
      const outcome = await shareImage(await renderShareCard(model), shareFileName(model), `${model.title} · ${model.time}`);
      if (outcome === "downloaded") toast({ title: t("saved"), description: t("savedDescription"), tone: "success" });
    } catch {
      toast({ title: t("failed"), tone: "error" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Tooltip content={text}>
      <IconButton aria-label={text} variant="ghost" onClick={handleClick} disabled={busy}>
        <Share2 aria-hidden />
      </IconButton>
    </Tooltip>
  );
}
