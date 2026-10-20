import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Button, Input } from "../../components/ui";
import { useLanguage } from "../../i18n/useLanguage";
import { useTheme } from "../../theme/useTheme";
import { AuthLayout } from "./AuthLayout";
import { NewPasswordFields } from "./NewPasswordFields";
import { isNewPasswordReady } from "./passwordPolicy";
import { useSignup } from "./useAuth";

export function SignupPage() {
  const { t } = useTranslation("auth");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const signup = useSignup();
  const { language } = useLanguage();
  const { mode } = useTheme();
  const navigate = useNavigate();
  // The page that bounced us here (e.g. an invite link); signing up should land back on it.
  const from = (useLocation().state as { from?: string } | null)?.from;

  const canSubmit = displayName !== "" && email !== "" && isNewPasswordReady(password, confirmPassword);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    try {
      await signup.mutateAsync({ email, password, display_name: displayName, locale: language, theme: mode });
      navigate(from ?? "/", { replace: true });
    } catch {
      // surfaced via signup.error below
    }
  }

  return (
    <AuthLayout title={t("signup.title")} subtitle={t("signup.subtitle")}>
      <form className="auth__form" onSubmit={handleSubmit}>
        <Input
          label={t("signup.displayName")}
          autoComplete="name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          required
        />
        <Input
          label={t("signup.email")}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <NewPasswordFields
          password={password}
          confirmation={confirmPassword}
          onPasswordChange={setPassword}
          onConfirmationChange={setConfirmPassword}
          passwordLabel={t("signup.password")}
          confirmationLabel={t("signup.confirmPassword")}
        />
        {signup.error && (
          <p role="alert">
            {errorMessage(signup.error, {
              409: t("signup.errors.emailTaken"),
              429: t("signup.errors.tooManyAttempts"),
            })}
          </p>
        )}
        <Button type="submit" size="lg" block loading={signup.isPending} disabled={!canSubmit}>
          {signup.isPending ? t("signup.submitting") : t("signup.submit")}
        </Button>
      </form>
      <p className="auth__switch">
        {t("signup.haveAccount")} <Link to="/login" state={from ? { from } : undefined}>
          {t("signup.loginLink")}
        </Link>
      </p>
    </AuthLayout>
  );
}
