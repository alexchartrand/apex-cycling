import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { createFormatters, type Formatters } from "./format";
import { toLanguage } from "./language";

/** Formatters for the current UI language; re-created only on language change. */
export function useFormat(): Formatters {
  const { i18n } = useTranslation();
  const language = toLanguage(i18n.resolvedLanguage ?? i18n.language);
  return useMemo(() => createFormatters(language), [language]);
}
