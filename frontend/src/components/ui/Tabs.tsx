import type { ReactNode } from "react";
import { Tabs as RadixTabs } from "radix-ui";
import "./Tabs.css";

export type TabItem<T extends string> = { value: T; label: ReactNode; icon?: ReactNode; count?: number };

/**
 * Underlined tab bar + panels. Controlled, so a page can mirror the active
 * tab into the URL (e.g. session detail ?tab=laps).
 */
export function Tabs<T extends string>({
  items,
  value,
  onValueChange,
  children,
  "aria-label": ariaLabel,
}: {
  items: TabItem<T>[];
  value: T;
  onValueChange: (value: T) => void;
  children: ReactNode;
  "aria-label": string;
}) {
  return (
    <RadixTabs.Root className="tabs" value={value} onValueChange={(next) => onValueChange(next as T)}>
      <RadixTabs.List className="tabs__list" aria-label={ariaLabel}>
        {items.map((item) => (
          <RadixTabs.Trigger key={item.value} value={item.value} className="tabs__trigger">
            {item.icon}
            <span>{item.label}</span>
            {item.count != null && <span className="tabs__count">{item.count}</span>}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  );
}

export function TabPanel({ value, children }: { value: string; children: ReactNode }) {
  return (
    <RadixTabs.Content value={value} className="tabs__panel">
      {children}
    </RadixTabs.Content>
  );
}
