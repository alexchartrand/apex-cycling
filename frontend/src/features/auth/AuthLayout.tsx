import type { ReactNode } from "react";
import wordmark from "../../brand/wordmark.svg";
import { Card } from "../../components/ui";
import "./AuthLayout.css";

export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="auth-page">
      <img src={wordmark} alt="ApexCycling" className="auth-page__logo" />
      <Card>
        <h1>{title}</h1>
        {children}
      </Card>
    </div>
  );
}
