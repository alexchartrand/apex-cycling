import { useMutation } from "@tanstack/react-query";
import { MailCheck, ShieldQuestion } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Button, EmptyState, Input } from "../../components/ui";
import { requestPasswordReset } from "./api";
import { AuthLayout } from "./AuthLayout";

export function ForgotPasswordPage() {
  const { t } = useTranslation("auth");
  const [email, setEmail] = useState("");
  const request = useMutation({ mutationFn: requestPasswordReset });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    request.mutate(email);
  }

  const sent = request.data;

  return (
    <AuthLayout title={t("forgot.title")} subtitle={sent ? undefined : t("forgot.subtitle")}>
      {sent ? (
        <EmptyState
          compact
          icon={sent.email_enabled ? <MailCheck aria-hidden /> : <ShieldQuestion aria-hidden />}
          title={sent.email_enabled ? t("forgot.sentTitle") : t("forgot.noEmailTitle")}
          description={sent.email_enabled ? t("forgot.sent", { email }) : t("forgot.noEmail")}
        />
      ) : (
        <form className="auth__form" onSubmit={handleSubmit}>
          <Input
            label={t("forgot.email")}
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          {request.error && <p role="alert">{errorMessage(request.error, { 429: t("forgot.tooManyAttempts") })}</p>}
          <Button type="submit" size="lg" block loading={request.isPending}>
            {request.isPending ? t("forgot.submitting") : t("forgot.submit")}
          </Button>
        </form>
      )}
      <p className="auth__switch">
        <Link to="/login">{t("forgot.backToLogin")}</Link>
      </p>
    </AuthLayout>
  );
}
