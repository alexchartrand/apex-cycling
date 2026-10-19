import type { ButtonHTMLAttributes, ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { Link, type LinkProps } from "react-router-dom";
import "./Button.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** @deprecated use `size` — kept until every screen is restyled (T1.6). */
  scale?: "sm" | "md";
  icon?: ReactNode;
  iconRight?: ReactNode;
  loading?: boolean;
  block?: boolean;
};

export function Button({
  variant = "primary",
  size,
  scale,
  icon,
  iconRight,
  loading = false,
  block = false,
  className,
  children,
  disabled,
  type = "button",
  ...props
}: ButtonProps) {
  const resolvedSize = size ?? scale ?? "md";
  const classes = ["btn", `btn--${variant}`, `btn--${resolvedSize}`, block && "btn--block", className]
    .filter(Boolean)
    .join(" ");
  return (
    <button type={type} className={classes} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
      {loading ? <LoaderCircle className="btn__spinner" aria-hidden /> : icon}
      {children != null && <span className="btn__label">{children}</span>}
      {iconRight}
    </button>
  );
}

type IconButtonProps = Omit<ButtonProps, "icon" | "iconRight" | "children" | "block"> & {
  "aria-label": string;
  children: ReactNode;
};

/** Square, icon-only button. `aria-label` is required since there's no visible text. */
export function IconButton({ variant = "ghost", size = "md", className, children, ...props }: IconButtonProps) {
  return (
    <Button variant={variant} size={size} className={["btn--icon", className].filter(Boolean).join(" ")} {...props}>
      {children}
    </Button>
  );
}

type ButtonLinkProps = Omit<LinkProps, "className"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
  iconRight?: ReactNode;
  block?: boolean;
  className?: string;
};

/** A router link that looks like a Button (never nest a <button> in an <a>). */
export function ButtonLink({ variant = "primary", size = "md", icon, iconRight, block, className, children, ...props }: ButtonLinkProps) {
  const classes = ["btn", `btn--${variant}`, `btn--${size}`, block && "btn--block", className].filter(Boolean).join(" ");
  return (
    <Link className={classes} {...props}>
      {icon}
      {children != null && <span className="btn__label">{children}</span>}
      {iconRight}
    </Link>
  );
}
