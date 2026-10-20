import { useEffect, useState } from "react";
import { ChevronsLeft, ChevronsRight, Download, Languages, LogOut, Monitor, Moon, MoreHorizontal, Palette, Settings, ShieldCheck, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { BrandMark } from "../brand/BrandMark";
import { Wordmark } from "../brand/Wordmark";
import { useMyAthlete } from "../features/athletes/useAthlete";
import { useCoachingBadgeCount } from "../features/coaching/useCoaching";
import { useCurrentUser, useLogout } from "../features/auth/useAuth";
import { usePreferenceSetters } from "../features/auth/usePreferences";
import { COMPACT_SHELL_QUERY, useMediaQuery } from "../hooks/useMediaQuery";
import { SUPPORTED_LANGUAGES, type Language } from "../i18n/language";
import { useLanguage } from "../i18n/useLanguage";
import { useInstallPrompt } from "../pwa/installPrompt";
import { PwaStatus } from "../pwa/PwaStatus";
import type { ThemeMode } from "../theme/theme";
import { useTheme } from "../theme/useTheme";
import { LanguageSwitcher, ThemeSwitcher } from "./preferences/PreferenceSwitchers";
import { AthleteSwitcher } from "./shell/AthleteSwitcher";
import { ViewingBanner } from "./shell/ViewingBanner";
import {
  activeNavItem,
  MOBILE_TABS,
  MORE_SHEET_ITEMS,
  SIDEBAR_FOOTER,
  SIDEBAR_GROUPS,
  type NavItem,
  type NavKey,
} from "./shell/navigation";
import { Avatar, Button, Dialog, IconButton, Menu, MenuItem, MenuLabel, MenuRadioGroup, MenuSeparator, Tooltip } from "./ui";
import "./shell/AppShell.css";

const COLLAPSED_STORAGE_KEY = "apex-sidebar-collapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function AppShell() {
  const { t } = useTranslation("shell");
  const location = useLocation();
  const isCompact = useMediaQuery(COMPACT_SHELL_QUERY);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [moreOpen, setMoreOpen] = useState(false);
  const active = activeNavItem(location.pathname);
  // Requests and comments waiting for the user, shown on their nav item.
  const badges: Partial<Record<NavKey, number>> = { coach: useCoachingBadgeCount() };
  const sectionTitle = active ? t(`nav.${active.key}`) : t("nav.home");

  useEffect(() => {
    document.title = `${sectionTitle} · ApexCycling`;
  }, [sectionTitle]);

  // Close the More sheet on navigation.
  useEffect(() => setMoreOpen(false), [location.pathname]);

  function toggleCollapsed() {
    setCollapsed((current) => {
      try {
        localStorage.setItem(COLLAPSED_STORAGE_KEY, current ? "0" : "1");
      } catch {
        // non-persistent is fine
      }
      return !current;
    });
  }

  const sidebarCollapsed = collapsed && !isCompact;

  return (
    <div className={sidebarCollapsed ? "shell shell--collapsed" : "shell"}>
      <a href="#main-content" className="shell__skip">
        {t("skipToContent")}
      </a>

      <aside className="shell__sidebar">
        <Link to="/" className="shell__brand" aria-label="ApexCycling">
          {sidebarCollapsed ? <BrandMark size={36} /> : <Wordmark className="shell__wordmark" />}
        </Link>

        <AthleteSwitcher variant={sidebarCollapsed ? "compact" : "full"} />

        <nav className="shell__nav" aria-label={t("mainNavigation")}>
          {SIDEBAR_GROUPS.map((group, index) => (
            <div key={group.key ?? index} className="shell__nav-group">
              {group.key && !sidebarCollapsed && <div className="shell__nav-heading eyebrow">{t(`groups.${group.key}`)}</div>}
              {group.items.map((item) => (
                <SidebarLink
                  key={item.key}
                  item={item}
                  active={active?.key === item.key}
                  collapsed={sidebarCollapsed}
                  badge={badges[item.key]}
                />
              ))}
            </div>
          ))}
        </nav>

        <div className="shell__sidebar-footer">
          {SIDEBAR_FOOTER.map((item) => (
            <SidebarLink key={item.key} item={item} active={active?.key === item.key} collapsed={sidebarCollapsed} />
          ))}
          <AccountMenu variant={sidebarCollapsed ? "compact" : "full"} />
          <Tooltip content={sidebarCollapsed ? t("expandSidebar") : t("collapseSidebar")} side="right">
            <IconButton
              aria-label={sidebarCollapsed ? t("expandSidebar") : t("collapseSidebar")}
              size="sm"
              className="shell__collapse"
              onClick={toggleCollapsed}
            >
              {sidebarCollapsed ? <ChevronsRight aria-hidden /> : <ChevronsLeft aria-hidden />}
            </IconButton>
          </Tooltip>
        </div>
      </aside>

      <div className="shell__body">
        <PwaStatus />
        <header className="shell__topbar">
          <Link to="/" aria-label="ApexCycling">
            <BrandMark size={32} />
          </Link>
          <span className="shell__topbar-title">{sectionTitle}</span>
          <AthleteSwitcher variant="avatar" />
          <AccountMenu variant="avatar" />
        </header>
        <ViewingBanner />

        <main id="main-content" className="shell__main" tabIndex={-1}>
          <div className="shell__content">
            <Outlet />
          </div>
        </main>

        <nav className="shell__tabbar" aria-label={t("mainNavigation")}>
          {MOBILE_TABS.map((item) => {
            const Icon = item.icon;
            const isActive = active?.key === item.key;
            return (
              <NavLink
                key={item.key}
                to={item.to}
                className={isActive ? "shell__tab shell__tab--active" : "shell__tab"}
                aria-current={isActive ? "page" : undefined}
              >
                <Icon aria-hidden />
                <span>{t(`nav.${item.key}`)}</span>
              </NavLink>
            );
          })}
          <button
            type="button"
            className={
              active && MORE_SHEET_ITEMS.some((i) => i.key === active.key) ? "shell__tab shell__tab--active" : "shell__tab"
            }
            onClick={() => setMoreOpen(true)}
          >
            <MoreHorizontal aria-hidden />
            <span>{t("nav.more")}</span>
            {MORE_SHEET_ITEMS.some((i) => badges[i.key]) && <span className="shell__dot" aria-hidden />}
          </button>
        </nav>
      </div>

      <MoreSheet open={moreOpen} onOpenChange={setMoreOpen} activeKey={active?.key} badges={badges} />
    </div>
  );
}

function NavBadge({ count }: { count: number | undefined }) {
  const { t } = useTranslation("shell");
  if (!count) return null;
  return (
    <span className="shell__badge" aria-label={t("waitingCount", { count })}>
      {count > 9 ? "9+" : count}
    </span>
  );
}

function SidebarLink({
  item,
  active,
  collapsed,
  badge,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  badge?: number;
}) {
  const { t } = useTranslation("shell");
  const Icon = item.icon;
  const label = t(`nav.${item.key}`);
  const link = (
    <NavLink
      to={item.to}
      className={active ? "shell__link shell__link--active" : "shell__link"}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? label : undefined}
    >
      <Icon aria-hidden />
      {!collapsed && <span>{label}</span>}
      {collapsed ? badge ? <span className="shell__dot" aria-hidden /> : null : <NavBadge count={badge} />}
    </NavLink>
  );
  return collapsed ? (
    <Tooltip content={label} side="right">
      {link}
    </Tooltip>
  ) : (
    link
  );
}

function MoreSheet({
  open,
  onOpenChange,
  activeKey,
  badges,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  activeKey: string | undefined;
  badges: Partial<Record<NavKey, number>>;
}) {
  const { t } = useTranslation("shell");
  const { install } = useInstallPrompt();
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={t("moreTitle")}>
      <div className="shell__more-grid">
        {MORE_SHEET_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.key}
              to={item.to}
              className={activeKey === item.key ? "shell__more-item shell__more-item--active" : "shell__more-item"}
            >
              <Icon aria-hidden />
              <span>{t(`nav.${item.key}`)}</span>
              <NavBadge count={badges[item.key]} />
            </Link>
          );
        })}
      </div>
      <div className="shell__more-prefs">
        <span className="eyebrow">{t("preferences")}</span>
        <div className="shell__more-prefs-row">
          <LanguageSwitcher size="md" />
          <ThemeSwitcher size="md" showLabels />
        </div>
        {install && (
          <Button variant="secondary" icon={<Download aria-hidden />} onClick={install}>
            {t("pwa.install")}
          </Button>
        )}
      </div>
    </Dialog>
  );
}

const THEME_ICONS: Record<ThemeMode, React.ReactNode> = {
  system: <Monitor aria-hidden />,
  light: <Sun aria-hidden />,
  dark: <Moon aria-hidden />,
};

function AccountMenu({ variant }: { variant: "full" | "compact" | "avatar" }) {
  const { t } = useTranslation(["shell", "common", "auth"]);
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const athlete = useMyAthlete();
  const logout = useLogout();
  const { language } = useLanguage();
  const { mode } = useTheme();
  // The persisting setters: a choice made here also saves to the account, so it survives a reload.
  const { setLanguage, setTheme } = usePreferenceSetters();
  const { install } = useInstallPrompt();
  const name = athlete.data?.display_name ?? user?.email ?? "";

  const trigger =
    variant === "full" ? (
      <button type="button" className="shell__account" aria-label={t("accountMenu")}>
        <Avatar name={name} />
        <span className="shell__account-text">
          <span className="shell__account-name">{name}</span>
          <span className="shell__account-meta">{user?.email}</span>
        </span>
      </button>
    ) : (
      <Button variant="ghost" className="shell__account-avatar" aria-label={t("accountMenu")}>
        <Avatar name={name} size="sm" />
      </Button>
    );

  return (
    <Menu trigger={trigger} align={variant === "avatar" ? "end" : "start"}>
      <MenuItem icon={<Settings aria-hidden />} onSelect={() => navigate("/settings")}>
        {t("shell:nav.settings")}
      </MenuItem>
      {user?.is_platform_admin && (
        <MenuItem icon={<ShieldCheck aria-hidden />} onSelect={() => navigate("/admin")}>
          {t("shell:nav.admin")}
        </MenuItem>
      )}
      <MenuSeparator />
      <MenuLabel>
        <Languages aria-hidden className="shell__menu-label-icon" /> {t("common:language")}
      </MenuLabel>
      <MenuRadioGroup<Language>
        value={language}
        onValueChange={setLanguage}
        options={SUPPORTED_LANGUAGES.map((lng) => ({ value: lng, label: t(`common:languages.${lng}`) }))}
      />
      <MenuSeparator />
      <MenuLabel>
        <Palette aria-hidden className="shell__menu-label-icon" /> {t("common:theme")}
      </MenuLabel>
      <MenuRadioGroup<ThemeMode>
        value={mode}
        onValueChange={setTheme}
        options={(["system", "light", "dark"] as const).map((value) => ({
          value,
          label: t(`common:themes.${value}`),
          icon: THEME_ICONS[value],
        }))}
      />
      <MenuSeparator />
      {install && (
        <MenuItem icon={<Download aria-hidden />} onSelect={install}>
          {t("shell:pwa.install")}
        </MenuItem>
      )}
      <MenuItem icon={<LogOut aria-hidden />} tone="danger" onSelect={() => logout.mutate()} disabled={logout.isPending}>
        {t("auth:logout")}
      </MenuItem>
    </Menu>
  );
}
