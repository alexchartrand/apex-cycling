import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Button, Input } from "../../components/ui";
import { AuthLayout } from "./AuthLayout";
import { isPasswordStrong, passwordStrengthErrors } from "./passwordPolicy";
import { useSignup } from "./useAuth";

export function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const signup = useSignup();
  const navigate = useNavigate();

  const strengthErrors = passwordStrengthErrors(password);
  const passwordTouched = password.length > 0;
  const mismatch = confirmPassword.length > 0 && confirmPassword !== password;
  const canSubmit =
    displayName !== "" && email !== "" && isPasswordStrong(password) && password === confirmPassword;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    try {
      await signup.mutateAsync({ email, password, display_name: displayName });
      navigate("/", { replace: true });
    } catch {
      // error surfaced via signup.error below
    }
  }

  return (
    <AuthLayout title="Create your account">
      <form onSubmit={handleSubmit}>
        <p>No club or invite needed — you'll be able to self-report transponder usage right away.</p>
        <Input
          label="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          required
        />
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {passwordTouched && strengthErrors.length > 0 && (
          <p className="ui-card__hint">Password needs: {strengthErrors.join("; ")}</p>
        )}
        <Input
          label="Confirm password"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
        />
        {mismatch && <p role="alert">Passwords don't match</p>}
        {signup.error && (
          <p role="alert">{signup.error instanceof ApiError ? signup.error.message : "Signup failed"}</p>
        )}
        <Button type="submit" disabled={signup.isPending || !canSubmit}>
          {signup.isPending ? "Creating account…" : "Sign up"}
        </Button>
      </form>
      <p>
        Already have an account? <a href="/login">Log in</a>
      </p>
    </AuthLayout>
  );
}
