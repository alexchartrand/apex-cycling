import {
  BarChart3,
  ClipboardList,
  Bike,
  CalendarDays,
  CloudDownload,
  Dumbbell,
  Flag,
  Gauge,
  Home,
  LineChart,
  ListChecks,
  Milestone,
  Settings,
  Sparkles,
  Trophy,
  Users,
  Wrench,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { pageShown, type Sport } from "../../features/sports/registry";

/** A page the navigation can point at. */
export type NavKey =
  | "home"
  | "log"
  | "records"
  | "progress"
  | "power"
  | "season"
  | "workouts"
  | "plans"
  | "aiCoach"
  | "tools"
  | "aero"
  | "equipment"
  | "coach"
  | "club"
  | "import"
  | "settings";

/**
 * What decides whether a page is shown to this viewer: optional features an
 * admin turned on, and the sports the athlete does (`features/sports`).
 */
export type NavContext = { aiCoach: boolean; sports: ReadonlySet<Sport> };

export type NavItem = {
  key: NavKey;
  to: string;
  icon: LucideIcon;
  /** Other path prefixes that belong to this page (detail pages, legacy URLs). */
  alsoMatches?: string[];
  /** Shown only when this holds; always shown without it. */
  requires?: (ctx: NavContext) => boolean;
};

export const NAV_ITEMS: Record<NavKey, NavItem> = {
  home: { key: "home", to: "/", icon: Home },
  log: { key: "log", to: "/log", icon: CalendarDays, alsoMatches: ["/sessions", "/activities", "/compare"] },
  plans: { key: "plans", to: "/plans", icon: Milestone },
  workouts: { key: "workouts", to: "/workouts", icon: ListChecks },
  season: { key: "season", to: "/season", icon: Flag },
  aiCoach: { key: "aiCoach", to: "/ai-coach", icon: Sparkles, requires: (ctx) => ctx.aiCoach },
  progress: { key: "progress", to: "/progress", icon: LineChart },
  records: { key: "records", to: "/records", icon: Trophy },
  power: { key: "power", to: "/power", icon: Gauge },
  aero: { key: "aero", to: "/aero", icon: Zap },
  equipment: { key: "equipment", to: "/equipment", icon: Bike },
  tools: { key: "tools", to: "/tools", icon: Wrench },
  club: { key: "club", to: "/club", icon: Users, alsoMatches: ["/join"] },
  coach: { key: "coach", to: "/coach", icon: ClipboardList },
  import: { key: "import", to: "/import", icon: CloudDownload },
  settings: { key: "settings", to: "/settings", icon: Settings },
};

export type HubKey = "home" | "log" | "train" | "progress" | "gear" | "club" | "coach" | "import" | "settings";

/**
 * A top-level navigation entry. A hub with several pages links to the first
 * one shown and lists its pages as sub-tabs; the pages keep their own URLs.
 */
export type NavHub = { key: HubKey; icon: LucideIcon; items: NavItem[] };

function single(key: NavKey & HubKey): NavHub {
  return { key, icon: NAV_ITEMS[key].icon, items: [NAV_ITEMS[key]] };
}

export const HUBS: Record<HubKey, NavHub> = {
  home: single("home"),
  log: single("log"),
  train: {
    key: "train",
    icon: Dumbbell,
    items: [NAV_ITEMS.plans, NAV_ITEMS.workouts, NAV_ITEMS.season, NAV_ITEMS.aiCoach],
  },
  progress: {
    key: "progress",
    icon: BarChart3,
    items: [NAV_ITEMS.progress, NAV_ITEMS.records, NAV_ITEMS.power, NAV_ITEMS.aero],
  },
  gear: { key: "gear", icon: Bike, items: [NAV_ITEMS.equipment, NAV_ITEMS.tools] },
  club: single("club"),
  coach: single("coach"),
  import: single("import"),
  settings: single("settings"),
};

export type NavGroup = { key: "analysis" | "team" | null; hubs: NavHub[] };

/** Desktop sidebar, top to bottom. */
export const SIDEBAR_GROUPS: NavGroup[] = [
  { key: null, hubs: [HUBS.home, HUBS.log, HUBS.train, HUBS.progress, HUBS.gear] },
  { key: "team", hubs: [HUBS.club, HUBS.coach] },
];

export const SIDEBAR_FOOTER: NavHub[] = [HUBS.import, HUBS.settings];

/** Phone bottom tabs; everything else lives in the "More" sheet. */
export const MOBILE_TABS: NavHub[] = [HUBS.home, HUBS.log, HUBS.train, HUBS.progress];

export const MORE_SHEET_ITEMS: NavItem[] = [
  NAV_ITEMS.equipment,
  NAV_ITEMS.tools,
  NAV_ITEMS.club,
  NAV_ITEMS.coach,
  NAV_ITEMS.import,
  NAV_ITEMS.settings,
];

/** Whether this viewer gets a page: its own condition, and a sport that needs it. */
export function itemShown(item: NavItem, ctx: NavContext): boolean {
  return (item.requires?.(ctx) ?? true) && pageShown(item.key, ctx.sports);
}

/** A hub's pages this viewer gets. */
export function shownItems(hub: NavHub, ctx: NavContext): NavItem[] {
  return hub.items.filter((item) => itemShown(item, ctx));
}

/** Where a hub's own link goes: its first page shown, else its first page. */
export function hubTarget(hub: NavHub, ctx: NavContext): string {
  return (shownItems(hub, ctx)[0] ?? hub.items[0]).to;
}

function matchesPrefix(pathname: string, prefix: string): boolean {
  if (prefix === "/") return pathname === "/";
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/** The page a URL belongs to, for highlighting and the page title. */
export function activeNavItem(pathname: string): NavItem | undefined {
  return Object.values(NAV_ITEMS).find((item) =>
    [item.to, ...(item.alsoMatches ?? [])].some((prefix) => matchesPrefix(pathname, prefix)),
  );
}

/** The hub a URL belongs to. */
export function activeHub(pathname: string): NavHub | undefined {
  const item = activeNavItem(pathname);
  if (!item) return undefined;
  return Object.values(HUBS).find((hub) => hub.items.some((candidate) => candidate.key === item.key));
}
