import { useQuery } from "@tanstack/react-query";
import { LinkIcon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Button, ButtonLink, EmptyState, useToast } from "../../components/ui";
import { checkPasswordResetToken } from "./api";
import { AuthLayout } from "./AuthLayout";
import { NewPasswordFields } from "./NewPasswordFields";
import { isNewPasswordReady } from "./passwordPolicy";
import { useConfirmPasswordReset } from "./useAuth";

/** The token travels in the URL fragment (#token=…) so it never reaches server logs or Referer headers. */
function readToken(): string {
  return new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
}

export function ResetPasswordPage() {
  const { t } = useTranslation("auth");
  const navigate = useNavigate();
  const { toast } = useToast();
  // Captured once: the fragment is scrubbed from the address bar below.
  const [token] = useState(readToken);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const confirm = useConfirmPasswordReset();

  const check = useQuery({
    queryKey: ["auth", "reset-token", token],
    queryFn: () => {
      window.history.replaceState(null, "", window.location.pathname);
      return checkPasswordResetToken(token);
    },
    enabled: token !== "",
    retry: false,
    staleTime: Infinity,
  });

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await confirm.mutateAsync({ token, new_password: password });
      toast({ title: t("reset.done"), tone: "success" });
      navigate("/", { replace: true });
    } catch {
      // surfaced via confirm.error below
    }
  }

  if (token === "" || check.isError) {
    return (
      <AuthLayout title={t("reset.title")}>
        <EmptyState
          compact
          icon={<LinkIcon aria-hidden />}
          title={t("reset.invalidTitle")}
          description={t("reset.invalid")}
          action={<ButtonLink to="/forgot-password">{t("reset.requestNew")}</ButtonLink>}
        />
        <p className="auth__switch">
          <Link to="/login">{t("forgot.backToLogin")}</Link>
        </p>
      </AuthLayout>
    );
  }

  if (!check.data) {
    return (
      <AuthLayout title={t("reset.title")}>
        <p role="status">{t("reset.checking")}</p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={t("reset.title")} subtitle={t("reset.subtitle", { email: check.data.email })}>
      <form className="auth__form" onSubmit={handleSubmit}>
        <NewPasswordFields
          password={password}
          confirmation={confirmation}
          onPasswordChange={setPassword}
          onConfirmationChange={setConfirmation}
          passwordLabel={t("reset.password")}
          confirmationLabel={t("reset.confirmPassword")}
        />
        {confirm.error && <p role="alert">{errorMessage(confirm.error, { 400: t("reset.invalid") })}</p>}
        <Button type="submit" size="lg" block loading={confirm.isPending} disabled={!isNewPasswordReady(password, confirmation)}>
          {confirm.isPending ? t("reset.submitting") : t("reset.submit")}
        </Button>
      </form>
    </AuthLayout>
  );
}
