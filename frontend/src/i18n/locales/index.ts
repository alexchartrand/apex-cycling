import enAuth from "./en/auth";
import enCommon from "./en/common";
import enShell from "./en/shell";
import frAuth from "./fr/auth";
import frCommon from "./fr/common";
import frShell from "./fr/shell";

export const resources = {
  en: { common: enCommon, auth: enAuth, shell: enShell },
  fr: { common: frCommon, auth: frAuth, shell: frShell },
} as const;

export const NAMESPACES = Object.keys(resources.en) as (keyof typeof resources.en)[];
