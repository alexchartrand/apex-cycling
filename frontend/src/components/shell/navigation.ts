import {
  BarChart3,
  ClipboardList,
  Bike,
  CalendarDays,
  CloudDownload,
  Home,
  Settings,
  Trophy,
  Users,
  Wrench,
  Zap,
  type LucideIcon,
} from "lucide-react";

export type NavKey =
  | "home"
  | "log"
  | "records"
  | "progress"
  | "tools"
  | "aero"
  | "equipment"
  | "coach"
  | "club"
  | "import"
  | "settings";

export type NavItem = {
  key: NavKey;
  to: string;
  icon: LucideIcon;
  /** Other path prefixes that belong to this section (detail pages, legacy URLs). */
  alsoMatches?: string[];
};

export type NavGroup = { key: "training" | "analysis" | "team" | null; items: NavItem[] };

export const NAV_ITEMS: Record<NavKey, NavItem> = {
  home: { key: "home", to: "/", icon: Home },
  log: { key: "log", to: "/log", icon: CalendarDays, alsoMatches: ["/sessions", "/activities"] },
  records: { key: "records", to: "/records", icon: Trophy },
  progress: { key: "progress", to: "/progress", icon: BarChart3 },
  tools: { key: "tools", to: "/tools", icon: Wrench },
  aero: { key: "aero", to: "/aero", icon: Zap },
  equipment: { key: "equipment", to: "/equipment", icon: Bike },
  coach: { key: "coach", to: "/coach", icon: ClipboardList },
  club: { key: "club", to: "/club", icon: Users, alsoMatches: ["/join"] },
  import: { key: "import", to: "/import", icon: CloudDownload },
  settings: { key: "settings", to: "/settings", icon: Settings },
};

/** Desktop sidebar, top to bottom. */
export const SIDEBAR_GROUPS: NavGroup[] = [
  { key: null, items: [NAV_ITEMS.home, NAV_ITEMS.log, NAV_ITEMS.records, NAV_ITEMS.progress] },
  { key: "analysis", items: [NAV_ITEMS.tools, NAV_ITEMS.aero, NAV_ITEMS.equipment] },
  { key: "team", items: [NAV_ITEMS.club, NAV_ITEMS.coach] },
];

export const SIDEBAR_FOOTER: NavItem[] = [NAV_ITEMS.import, NAV_ITEMS.settings];

/** Phone bottom tabs; everything else lives in the "More" sheet. */
export const MOBILE_TABS: NavItem[] = [NAV_ITEMS.home, NAV_ITEMS.log, NAV_ITEMS.records, NAV_ITEMS.tools];

export const MORE_SHEET_ITEMS: NavItem[] = [
  NAV_ITEMS.progress,
  NAV_ITEMS.aero,
  NAV_ITEMS.equipment,
  NAV_ITEMS.import,
  NAV_ITEMS.club,
  NAV_ITEMS.coach,
  NAV_ITEMS.settings,
];

function matchesPrefix(pathname: string, prefix: string): boolean {
  if (prefix === "/") return pathname === "/";
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/** The nav section a URL belongs to, for highlighting and the page title. */
export function activeNavItem(pathname: string): NavItem | undefined {
  return Object.values(NAV_ITEMS).find((item) =>
    [item.to, ...(item.alsoMatches ?? [])].some((prefix) => matchesPrefix(pathname, prefix)),
  );
}
