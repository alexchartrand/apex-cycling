import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Button, Input } from "../../components/ui";
import { AuthLayout } from "./AuthLayout";
import { failedPasswordRules, isPasswordStrong, PASSWORD_RULE_COUNTS } from "./passwordPolicy";
import { useSignup } from "./useAuth";

export function SignupPage() {
  const { t } = useTranslation("auth");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const signup = useSignup();
  const navigate = useNavigate();

  const failedRules = failedPasswordRules(password);
  const mismatch = confirmPassword.length > 0 && confirmPassword !== password;
  const canSubmit = displayName !== "" && email !== "" && isPasswordStrong(password) && password === confirmPassword;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    try {
      await signup.mutateAsync({ email, password, display_name: displayName });
      navigate("/", { replace: true });
    } catch {
      // surfaced via signup.error below
    }
  }

  const passwordHint =
    password.length > 0 && failedRules.length > 0 ? (
      <>
        {t("signup.passwordNeeds")}
        <ul className="auth__rules">
          {failedRules.map((rule) => (
            <li key={rule}>{t(`passwordRules.${rule}`, { count: PASSWORD_RULE_COUNTS[rule] })}</li>
          ))}
        </ul>
      </>
    ) : undefined;

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
        <Input
          label={t("signup.password")}
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          hint={passwordHint}
          required
        />
        <Input
          label={t("signup.confirmPassword")}
          type="password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          error={mismatch ? t("signup.mismatch") : undefined}
          required
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
        {t("signup.haveAccount")} <Link to="/login">{t("signup.loginLink")}</Link>
      </p>
    </AuthLayout>
  );
}
