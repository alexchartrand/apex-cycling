import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Button, Input } from "../../components/ui";
import { AuthLayout } from "./AuthLayout";
import { useLogin } from "./useAuth";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const login = useLogin();
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await login.mutateAsync({ email, password, remember_me: rememberMe });
      navigate("/", { replace: true });
    } catch {
      // error surfaced via login.error below
    }
  }

  return (
    <AuthLayout title="Log in">
      <form onSubmit={handleSubmit}>
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
        <label className="auth-page__checkbox-row">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />
          Keep me logged in
        </label>
        {login.error && (
          <p role="alert">{login.error instanceof ApiError ? login.error.message : "Login failed"}</p>
        )}
        <Button type="submit" disabled={login.isPending}>
          {login.isPending ? "Logging in…" : "Log in"}
        </Button>
      </form>
      <p>
        No account? <a href="/signup">Sign up</a>
      </p>
    </AuthLayout>
  );
}
