import { useTranslation } from "react-i18next";
import { Input } from "../../components/ui";
import { failedPasswordRules, PASSWORD_RULE_COUNTS } from "./passwordPolicy";
import "./NewPasswordFields.css";

/** "New password" + "confirm" inputs, with the unmet strength rules listed live. */
export function NewPasswordFields({
  password,
  confirmation,
  onPasswordChange,
  onConfirmationChange,
  passwordLabel,
  confirmationLabel,
}: {
  password: string;
  confirmation: string;
  onPasswordChange: (value: string) => void;
  onConfirmationChange: (value: string) => void;
  passwordLabel: string;
  confirmationLabel: string;
}) {
  const { t } = useTranslation("auth");
  const failedRules = failedPasswordRules(password);
  const mismatch = confirmation.length > 0 && confirmation !== password;

  const passwordHint =
    password.length > 0 && failedRules.length > 0 ? (
      <>
        {t("signup.passwordNeeds")}
        <ul className="password-rules">
          {failedRules.map((rule) => (
            <li key={rule}>{t(`passwordRules.${rule}`, { count: PASSWORD_RULE_COUNTS[rule] })}</li>
          ))}
        </ul>
      </>
    ) : undefined;

  return (
    <>
      <Input
        label={passwordLabel}
        type="password"
        autoComplete="new-password"
        value={password}
        onChange={(e) => onPasswordChange(e.target.value)}
        hint={passwordHint}
        required
      />
      <Input
        label={confirmationLabel}
        type="password"
        autoComplete="new-password"
        value={confirmation}
        onChange={(e) => onConfirmationChange(e.target.value)}
        error={mismatch ? t("signup.mismatch") : undefined}
        required
      />
    </>
  );
}
