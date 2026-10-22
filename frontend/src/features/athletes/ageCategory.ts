import type { TFunction } from "i18next";

const MASTERS_BAND_YEARS = 5;

const YOUTH_TO_ELITE = ["U11", "U13", "U15", "U17", "U19", "U23", "ELITE"];

/** Sort key putting categories in age order: youth, elite, then the masters bands. */
export function ageCategoryRank(code: string): number {
  const youth = YOUTH_TO_ELITE.indexOf(code);
  if (youth >= 0) return youth;
  const masters = /^M(\d+)$/.exec(code);
  return YOUTH_TO_ELITE.length + (masters ? Number(masters[1]) : 0);
}

/**
 * The backend's UCI category code (U11…U23, ELITE, M30, M35…) as a label:
 * youth/elite codes map 1:1, masters codes are five-year bands ("M35" →
 * "Master 35–39").
 */
export function ageCategoryLabel(code: string, t: TFunction<"common">): string {
  const masters = /^M(\d+)$/.exec(code);
  if (masters) {
    const from = Number(masters[1]);
    return t("ageCategories.master", { from, to: from + MASTERS_BAND_YEARS - 1 });
  }
  return t(`ageCategories.${code as "U11"}`, { defaultValue: code });
}
