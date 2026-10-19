import enAuth from "./en/auth";
import enCommon from "./en/common";
import frAuth from "./fr/auth";
import frCommon from "./fr/common";

export const resources = {
  en: { common: enCommon, auth: enAuth },
  fr: { common: frCommon, auth: frAuth },
} as const;

export const NAMESPACES = Object.keys(resources.en) as (keyof typeof resources.en)[];
