import type { ButtonHTMLAttributes } from "react";
import "./ui.css";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { scale?: "sm" | "md" };

export function Button({ scale = "md", className, ...props }: ButtonProps) {
  const classes = [scale === "sm" ? "btn--sm" : "", className].filter(Boolean).join(" ");
  return <button className={classes || undefined} {...props} />;
}
