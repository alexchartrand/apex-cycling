import type { ReactNode } from "react";
import "./Card.css";

type CardProps = {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  /** "flush" drops body padding, for edge-to-edge tables/charts. */
  padding?: "md" | "flush";
  as?: "div" | "section" | "article";
};

export function Card({ children, className, title, eyebrow, actions, padding = "md", as: Tag = "div" }: CardProps) {
  const classes = ["ui-card", padding === "flush" && "ui-card--flush", className].filter(Boolean).join(" ");
  const hasHeader = title != null || eyebrow != null || actions != null;
  return (
    <Tag className={classes}>
      {hasHeader && (
        <header className="ui-card__header">
          <div className="ui-card__heading">
            {eyebrow != null && <span className="eyebrow">{eyebrow}</span>}
            {title != null && <h3 className="ui-card__title">{title}</h3>}
          </div>
          {actions != null && <div className="ui-card__actions">{actions}</div>}
        </header>
      )}
      {children}
    </Tag>
  );
}
