import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Button, Card, Input } from "../../components/ui";
import { joinPath, tokenFromPasted } from "./inviteToken";

/** Paste an invitation link (or just its code) to go and accept it. */
export function JoinWithLink() {
  const { t } = useTranslation("club");
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [invalid, setInvalid] = useState(false);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const token = tokenFromPasted(text);
    if (!token) {
      setInvalid(true);
      return;
    }
    navigate(joinPath(token));
  }

  return (
    <Card as="section" title={t("joinWithLink.title")}>
      <form className="club-form club-form--inline" onSubmit={handleSubmit} noValidate>
        <Input
          label={t("joinWithLink.label")}
          placeholder={t("joinWithLink.placeholder")}
          value={text}
          autoComplete="off"
          error={invalid ? t("joinWithLink.invalid") : undefined}
          onChange={(e) => {
            setText(e.target.value);
            setInvalid(false);
          }}
        />
        <Button type="submit" variant="secondary" disabled={text.trim() === ""}>
          {t("joinWithLink.action")}
        </Button>
      </form>
    </Card>
  );
}
