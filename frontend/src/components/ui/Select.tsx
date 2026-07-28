import type { ReactNode, SelectHTMLAttributes } from "react";
import "./ui.css";

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & { label?: ReactNode; scale?: "sm" | "md" };

export function Select({ label, scale = "md", className, children, ...props }: SelectProps) {
  const classes = [scale === "sm" ? "field--sm" : "", className].filter(Boolean).join(" ");
  const select = (
    <select className={classes || undefined} {...props}>
      {children}
    </select>
  );
  if (!label) return select;
  return (
    <label>
      {label}
      {select}
    </label>
  );
}
