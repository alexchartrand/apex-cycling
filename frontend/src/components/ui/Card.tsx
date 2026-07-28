import type { ReactNode } from "react";
import "./Card.css";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={className ? `ui-card ${className}` : "ui-card"}>{children}</div>;
}
