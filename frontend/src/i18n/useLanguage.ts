import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { toLanguage, type Language } from "./language";

export function useLanguage(): { language: Language; setLanguage: (language: Language) => void } {
  const { i18n } = useTranslation();
  const setLanguage = useCallback((language: Language) => void i18n.changeLanguage(language), [i18n]);
  return { language: toLanguage(i18n.resolvedLanguage ?? i18n.language), setLanguage };
}
