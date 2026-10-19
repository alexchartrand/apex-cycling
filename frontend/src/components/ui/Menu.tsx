import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { DropdownMenu } from "radix-ui";
import "./Menu.css";

/** Dropdown menu (user menu, row actions…). Compose from the parts below. */
export function Menu({
  trigger,
  children,
  align = "end",
}: {
  trigger: ReactNode;
  children: ReactNode;
  align?: "start" | "center" | "end";
}) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>{trigger}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className="menu" align={align} sideOffset={6}>
          {children}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function MenuItem({
  icon,
  children,
  onSelect,
  tone = "default",
  disabled,
}: {
  icon?: ReactNode;
  children: ReactNode;
  onSelect?: () => void;
  tone?: "default" | "danger";
  disabled?: boolean;
}) {
  return (
    <DropdownMenu.Item
      className={tone === "danger" ? "menu__item menu__item--danger" : "menu__item"}
      onSelect={onSelect}
      disabled={disabled}
    >
      {icon}
      <span>{children}</span>
    </DropdownMenu.Item>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <DropdownMenu.Label className="menu__label">{children}</DropdownMenu.Label>;
}

export function MenuSeparator() {
  return <DropdownMenu.Separator className="menu__separator" />;
}

export function MenuRadioGroup<T extends string>({
  value,
  onValueChange,
  options,
}: {
  value: T;
  onValueChange: (value: T) => void;
  options: { value: T; label: ReactNode; icon?: ReactNode }[];
}) {
  return (
    <DropdownMenu.RadioGroup value={value} onValueChange={(next) => onValueChange(next as T)}>
      {options.map((option) => (
        <DropdownMenu.RadioItem key={option.value} value={option.value} className="menu__item">
          {option.icon}
          <span>{option.label}</span>
          <DropdownMenu.ItemIndicator className="menu__indicator">
            <Check aria-hidden />
          </DropdownMenu.ItemIndicator>
        </DropdownMenu.RadioItem>
      ))}
    </DropdownMenu.RadioGroup>
  );
}
