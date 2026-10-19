import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { SegmentedControl } from "../ui";
import { SUPPORTED_LANGUAGES, type Language } from "../../i18n/language";
import { useLanguage } from "../../i18n/useLanguage";
import type { ThemeMode } from "../../theme/theme";
import { useTheme } from "../../theme/useTheme";

export function LanguageSwitcher({ size = "sm" }: { size?: "sm" | "md" }) {
  const { t } = useTranslation();
  const { language, setLanguage } = useLanguage();
  return (
    <SegmentedControl<Language>
      size={size}
      aria-label={t("language")}
      value={language}
      onChange={setLanguage}
      options={SUPPORTED_LANGUAGES.map((lng) => ({ value: lng, label: lng.toUpperCase() }))}
    />
  );
}

export function ThemeSwitcher({ size = "sm", showLabels = false }: { size?: "sm" | "md"; showLabels?: boolean }) {
  const { t } = useTranslation();
  const { mode, setMode } = useTheme();
  const options: { value: ThemeMode; icon: React.ReactNode }[] = [
    { value: "system", icon: <Monitor aria-hidden /> },
    { value: "light", icon: <Sun aria-hidden /> },
    { value: "dark", icon: <Moon aria-hidden /> },
  ];
  return (
    <SegmentedControl<ThemeMode>
      size={size}
      aria-label={t("theme")}
      value={mode}
      onChange={setMode}
      options={options.map((o) => ({
        value: o.value,
        icon: o.icon,
        label: showLabels ? t(`themes.${o.value}`) : <span className="visually-hidden">{t(`themes.${o.value}`)}</span>,
      }))}
    />
  );
}
