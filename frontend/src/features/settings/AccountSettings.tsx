import { Download } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Button, Card, Dialog, Input, useToast } from "../../components/ui";
import { downloadDataExport } from "../auth/api";
import { NewPasswordFields } from "../auth/NewPasswordFields";
import { isNewPasswordReady } from "../auth/passwordPolicy";
import { useChangePassword, useDeleteAccount } from "../auth/useAuth";

function PasswordCard() {
  const { t } = useTranslation("settings");
  const { toast } = useToast();
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmation, setConfirmation] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await change.mutateAsync({ current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      setConfirmation("");
      toast({ title: t("account.password.changed"), tone: "success" });
    } catch {
      // surfaced via change.error below
    }
  }

  return (
    <Card title={t("account.password.title")} as="section">
      <form className="settings-form" onSubmit={handleSubmit}>
        <p className="settings-section__description">{t("account.password.description")}</p>
        <div className="settings-form__stack">
          <Input
            label={t("account.password.current")}
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
          />
          <NewPasswordFields
            password={next}
            confirmation={confirmation}
            onPasswordChange={setNext}
            onConfirmationChange={setConfirmation}
            passwordLabel={t("account.password.new")}
            confirmationLabel={t("account.password.confirm")}
          />
        </div>
        {change.error && (
          <p role="alert" className="settings-form__error">
            {errorMessage(change.error, {
              400: t("account.password.wrongCurrent"),
              429: t("account.password.tooManyAttempts"),
            })}
          </p>
        )}
        <div className="settings-form__actions">
          <Button type="submit" loading={change.isPending} disabled={current === "" || !isNewPasswordReady(next, confirmation)}>
            {t("account.password.submit")}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function ExportCard() {
  const { t } = useTranslation("settings");
  const { toast } = useToast();
  const [pending, setPending] = useState(false);

  async function handleExport() {
    setPending(true);
    try {
      await downloadDataExport();
    } catch (error) {
      toast({ title: t("account.export.failed"), description: errorMessage(error), tone: "error" });
    } finally {
      setPending(false);
    }
  }

  return (
    <Card title={t("account.export.title")} as="section">
      <p className="settings-section__description">{t("account.export.description")}</p>
      <div className="settings-form__actions">
        <Button variant="secondary" icon={<Download aria-hidden />} loading={pending} onClick={handleExport}>
          {t("account.export.submit")}
        </Button>
      </div>
    </Card>
  );
}

function DeleteCard() {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const navigate = useNavigate();
  const del = useDeleteAccount();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");

  function handleOpenChange(next: boolean) {
    if (del.isPending) return;
    setOpen(next);
    if (!next) {
      setPassword("");
      del.reset();
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await del.mutateAsync(password);
      toast({ title: t("account.delete.deleted"), tone: "success" });
      navigate("/login", { replace: true });
    } catch {
      // surfaced via del.error in the dialog
    }
  }

  return (
    <Card title={t("account.delete.title")} as="section" className="settings-danger">
      <p className="settings-section__description">{t("account.delete.description")}</p>
      <div className="settings-form__actions">
        <Button variant="danger" onClick={() => setOpen(true)}>
          {t("account.delete.submit")}
        </Button>
      </div>
      <Dialog
        open={open}
        onOpenChange={handleOpenChange}
        title={t("account.delete.dialogTitle")}
        description={t("account.delete.dialogDescription")}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => handleOpenChange(false)} disabled={del.isPending}>
              {tc("cancel")}
            </Button>
            <Button type="submit" form="delete-account-form" variant="danger" loading={del.isPending} disabled={password === ""}>
              {t("account.delete.confirm")}
            </Button>
          </>
        }
      >
        <form id="delete-account-form" className="settings-form" onSubmit={handleSubmit}>
          <Input
            label={t("account.delete.password")}
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={del.error ? errorMessage(del.error, { 400: t("account.delete.wrongPassword") }) : undefined}
            required
          />
        </form>
      </Dialog>
    </Card>
  );
}

export function AccountSettings() {
  return (
    <>
      <PasswordCard />
      <ExportCard />
      <DeleteCard />
    </>
  );
}
