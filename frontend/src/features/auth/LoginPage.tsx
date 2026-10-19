import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Button, Checkbox, Input } from "../../components/ui";
import { AuthLayout } from "./AuthLayout";
import { useLogin } from "./useAuth";

export function LoginPage() {
  const { t } = useTranslation("auth");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const login = useLogin();
  const navigate = useNavigate();
  // ProtectedRoute stashes the page that bounced us here.
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await login.mutateAsync({ email, password, remember_me: rememberMe });
      navigate(from, { replace: true });
    } catch {
      // surfaced via login.error below
    }
  }

  return (
    <AuthLayout title={t("login.title")} subtitle={t("login.subtitle")}>
      <form className="auth__form" onSubmit={handleSubmit}>
        <Input
          label={t("login.email")}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          label={t("login.password")}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Checkbox label={t("login.rememberMe")} checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />
        {login.error && (
          <p role="alert">
            {errorMessage(login.error, {
              401: t("login.errors.invalidCredentials"),
              429: t("login.errors.tooManyAttempts"),
            })}
          </p>
        )}
        <Button type="submit" size="lg" block loading={login.isPending}>
          {login.isPending ? t("login.submitting") : t("login.submit")}
        </Button>
      </form>
      <p className="auth__switch">
        {t("login.noAccount")} <Link to="/signup">{t("login.signupLink")}</Link>
      </p>
    </AuthLayout>
  );
}
