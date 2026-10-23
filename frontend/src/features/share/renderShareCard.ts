import { CARD_HEIGHT, CARD_WIDTH, drawShareCard, type ShareCardModel } from "./shareCard";

const FONTS_TO_LOAD = ['700 100px "Barlow Condensed"', '500 30px "Inter Variable"', '600 30px "Inter Variable"'];

/** The card as a PNG. Waits for the web fonts, or the canvas would draw the fallback. */
export async function renderShareCard(model: ShareCardModel): Promise<Blob> {
  try {
    await Promise.all(FONTS_TO_LOAD.map((font) => document.fonts.load(font)));
  } catch {
    // A font that fails to load only costs the typeface, not the card.
  }
  const canvas = document.createElement("canvas");
  canvas.width = CARD_WIDTH;
  canvas.height = CARD_HEIGHT;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas is not available");
  drawShareCard(ctx, model);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Couldn't encode the card"))), "image/png");
  });
}

export type ShareOutcome = "shared" | "downloaded" | "cancelled";

/**
 * Hands the PNG to the system share sheet where files can be shared (phones),
 * otherwise saves it. Closing the share sheet is "cancelled", not an error.
 */
export async function shareImage(blob: Blob, fileName: string, title: string): Promise<ShareOutcome> {
  const file = new File([blob], fileName, { type: "image/png" });
  if (typeof navigator.share === "function" && typeof navigator.canShare === "function" && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title });
      return "shared";
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return "cancelled";
      throw err;
    }
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return "downloaded";
}
