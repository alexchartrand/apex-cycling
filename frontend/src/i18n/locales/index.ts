import enAdmin from "./en/admin";
import enAuth from "./en/auth";
import enClub from "./en/club";
import enCoach from "./en/coach";
import enCommon from "./en/common";
import enHome from "./en/home";
import enImport from "./en/import";
import enRecords from "./en/records";
import enSettings from "./en/settings";
import enShell from "./en/shell";
import enTraining from "./en/training";
import frAdmin from "./fr/admin";
import frAuth from "./fr/auth";
import frClub from "./fr/club";
import frCoach from "./fr/coach";
import frCommon from "./fr/common";
import frHome from "./fr/home";
import frImport from "./fr/import";
import frRecords from "./fr/records";
import frSettings from "./fr/settings";
import frShell from "./fr/shell";
import frTraining from "./fr/training";

export const resources = {
  en: {
    common: enCommon,
    auth: enAuth,
    shell: enShell,
    home: enHome,
    training: enTraining,
    import: enImport,
    records: enRecords,
    settings: enSettings,
    club: enClub,
    coach: enCoach,
    admin: enAdmin,
  },
  fr: {
    common: frCommon,
    auth: frAuth,
    shell: frShell,
    home: frHome,
    training: frTraining,
    import: frImport,
    records: frRecords,
    settings: frSettings,
    club: frClub,
    coach: frCoach,
    admin: frAdmin,
  },
} as const;

export const NAMESPACES = Object.keys(resources.en) as (keyof typeof resources.en)[];
