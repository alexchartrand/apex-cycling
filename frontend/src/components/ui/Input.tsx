import type { InputHTMLAttributes, ReactNode } from "react";
import "./ui.css";

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label?: ReactNode; scale?: "sm" | "md" };

export function Input({ label, scale = "md", className, ...props }: InputProps) {
  const classes = [scale === "sm" ? "field--sm" : "", className].filter(Boolean).join(" ");
  const input = <input className={classes || undefined} {...props} />;
  if (!label) return input;
  return (
    <label>
      {label}
      {input}
    </label>
  );
}
