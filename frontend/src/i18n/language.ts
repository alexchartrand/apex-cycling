export const SUPPORTED_LANGUAGES = ["fr", "en"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

// Also the i18next-browser-languagedetector localStorage key.
export const LANGUAGE_STORAGE_KEY = "apex-lang";

export function toLanguage(value: string | undefined | null): Language {
  const base = value?.toLowerCase().split("-")[0];
  return base === "fr" ? "fr" : "en";
}

/** BCP-47 locale used for Intl formatting: Canadian variants for both. */
export function intlLocale(language: Language): string {
  return language === "fr" ? "fr-CA" : "en-CA";
}
