import type { ReactNode } from "react";
import { CloudDownload, Trophy, Wrench } from "lucide-react";
import { useTranslation } from "react-i18next";
import { BrandMark } from "../../brand/BrandMark";
import { Wordmark } from "../../brand/Wordmark";
import { LanguageSwitcher, ThemeSwitcher } from "../../components/preferences/PreferenceSwitchers";
import "./AuthLayout.css";

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  const { t } = useTranslation("auth");
  const features = [
    { icon: CloudDownload, text: t("layout.features.sqorz") },
    { icon: Trophy, text: t("layout.features.records") },
    { icon: Wrench, text: t("layout.features.tools") },
  ];

  return (
    <div className="auth">
      {/* Always ink, in both themes: the brand panel is a fixed "night" surface. */}
      <aside className="auth__brand" data-theme="dark">
        <Wordmark className="auth__wordmark" />
        <div className="auth__pitch">
          <p className="auth__tagline">{t("layout.tagline")}</p>
          <ul className="auth__features">
            {features.map(({ icon: Icon, text }) => (
              <li key={text}>
                <Icon aria-hidden />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <svg className="auth__track" viewBox="0 0 400 200" aria-hidden>
          <rect x="20" y="20" width="360" height="160" rx="80" />
          <rect x="34" y="34" width="332" height="132" rx="66" />
          <line x1="366" y1="100" x2="392" y2="100" />
        </svg>
      </aside>

      <main className="auth__main">
        <div className="auth__prefs">
          <LanguageSwitcher />
          <ThemeSwitcher />
        </div>
        <div className="auth__form-wrap">
          <BrandMark className="auth__mark" size={44} />
          <header className="auth__header">
            <h1>{title}</h1>
            {subtitle && <p className="auth__subtitle">{subtitle}</p>}
          </header>
          {children}
        </div>
      </main>
    </div>
  );
}
