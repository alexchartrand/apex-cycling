import type { ReactNode } from "react";
import "./EmptyState.css";

export function EmptyState({
  icon,
  title,
  description,
  action,
  compact = false,
}: {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "empty-state empty-state--compact" : "empty-state"}>
      {icon != null && <div className="empty-state__icon">{icon}</div>}
      <h3 className="empty-state__title">{title}</h3>
      {description != null && <p className="empty-state__description">{description}</p>}
      {action != null && <div className="empty-state__action">{action}</div>}
    </div>
  );
}
