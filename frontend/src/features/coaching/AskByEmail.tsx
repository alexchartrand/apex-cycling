import { useState, type FormEvent } from "react";
import { Button, Input } from "../../components/ui";

/**
 * One email field and a button. The backend answers an email request the same
 * whether or not the address has an account, so the caller words its success
 * message accordingly.
 */
export function AskByEmail({
  label,
  action,
  onSubmit,
  pending,
}: {
  label: string;
  action: string;
  onSubmit: (email: string) => Promise<void>;
  pending: boolean;
}) {
  const [email, setEmail] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    await onSubmit(trimmed);
    setEmail("");
  }

  return (
    <form className="coach-ask" onSubmit={handleSubmit}>
      <Input label={label} type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} />
      <Button type="submit" variant="secondary" loading={pending} disabled={email.trim() === ""}>
        {action}
      </Button>
    </form>
  );
}
