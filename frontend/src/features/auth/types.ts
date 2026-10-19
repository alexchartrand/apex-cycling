import type { Language } from "../../i18n/language";
import type { ThemeMode } from "../../theme/theme";

export interface User {
  id: string;
  email: string;
  is_platform_admin: boolean;
  /** Null = never chosen: the device keeps its own (browser language / system theme). */
  locale: Language | null;
  theme: ThemeMode | null;
}

export interface Preferences {
  locale?: Language | null;
  theme?: ThemeMode | null;
}

export interface SignupPayload {
  email: string;
  password: string;
  display_name: string;
  locale?: Language;
  theme?: ThemeMode;
}

export interface LoginPayload {
  email: string;
  password: string;
  remember_me: boolean;
}
