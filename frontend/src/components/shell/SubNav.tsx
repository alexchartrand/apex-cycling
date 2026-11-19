import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import "../ui/Tabs.css";
import "./SubNav.css";

export type SubNavItem = { key: string; to: string; label: ReactNode; active: boolean; icon?: ReactNode };

/**
 * A row of links styled as the tab bar: the pages of a hub, or the sections
 * of the coach view. Unlike `Tabs`, each entry is its own URL.
 */
export function SubNav({ items, "aria-label": ariaLabel, className }: { items: SubNavItem[]; "aria-label": string; className?: string }) {
  return (
    <nav className={className ? `subnav ${className}` : "subnav"} aria-label={ariaLabel}>
      <div className="tabs__list">
        {items.map((item) => (
          <Link
            key={item.key}
            to={item.to}
            className="tabs__trigger subnav__link"
            data-state={item.active ? "active" : "inactive"}
            aria-current={item.active ? "page" : undefined}
          >
            {item.icon}
            <span>{item.label}</span>
          </Link>
        ))}
      </div>
    </nav>
  );
}
