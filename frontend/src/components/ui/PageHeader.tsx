import type { ReactNode } from "react";
import { ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";
import "./PageHeader.css";

export function PageHeader({
  title,
  eyebrow,
  description,
  actions,
  back,
}: {
  title: ReactNode;
  eyebrow?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  back?: { to: string; label: ReactNode };
}) {
  return (
    <header className="page-header">
      {back && (
        <Link to={back.to} className="page-header__back">
          <ChevronLeft aria-hidden />
          {back.label}
        </Link>
      )}
      <div className="page-header__row">
        <div className="page-header__heading">
          {eyebrow != null && <span className="eyebrow">{eyebrow}</span>}
          <h1 className="page-header__title">{title}</h1>
          {description != null && <p className="page-header__description">{description}</p>}
        </div>
        {actions != null && <div className="page-header__actions">{actions}</div>}
      </div>
    </header>
  );
}
