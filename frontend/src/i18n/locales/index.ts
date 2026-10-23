import enActivities from "./en/activities";
import enAero from "./en/aero";
import enAdmin from "./en/admin";
import enAuth from "./en/auth";
import enClub from "./en/club";
import enCoach from "./en/coach";
import enCommon from "./en/common";
import enCompare from "./en/compare";
import enEquipment from "./en/equipment";
import enGoals from "./en/goals";
import enHome from "./en/home";
import enImport from "./en/import";
import enInsights from "./en/insights";
import enNotifications from "./en/notifications";
import enPlan from "./en/plan";
import enRecords from "./en/records";
import enShare from "./en/share";
import enSeason from "./en/season";
import enSettings from "./en/settings";
import enShell from "./en/shell";
import enTools from "./en/tools";
import enTraining from "./en/training";
import frActivities from "./fr/activities";
import frAero from "./fr/aero";
import frAdmin from "./fr/admin";
import frAuth from "./fr/auth";
import frClub from "./fr/club";
import frCoach from "./fr/coach";
import frCommon from "./fr/common";
import frCompare from "./fr/compare";
import frEquipment from "./fr/equipment";
import frGoals from "./fr/goals";
import frHome from "./fr/home";
import frImport from "./fr/import";
import frInsights from "./fr/insights";
import frNotifications from "./fr/notifications";
import frPlan from "./fr/plan";
import frRecords from "./fr/records";
import frShare from "./fr/share";
import frSeason from "./fr/season";
import frSettings from "./fr/settings";
import frShell from "./fr/shell";
import frTools from "./fr/tools";
import frTraining from "./fr/training";

export const resources = {
  en: {
    common: enCommon,
    compare: enCompare,
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
    tools: enTools,
    activities: enActivities,
    aero: enAero,
    equipment: enEquipment,
    goals: enGoals,
    plan: enPlan,
    insights: enInsights,
    share: enShare,
    notifications: enNotifications,
    season: enSeason,
  },
  fr: {
    common: frCommon,
    compare: frCompare,
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
    tools: frTools,
    activities: frActivities,
    aero: frAero,
    equipment: frEquipment,
    goals: frGoals,
    plan: frPlan,
    insights: frInsights,
    share: frShare,
    notifications: frNotifications,
    season: frSeason,
  },
} as const;

export const NAMESPACES = Object.keys(resources.en) as (keyof typeof resources.en)[];
