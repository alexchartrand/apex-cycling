import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useLogin } from "./useAuth";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await login.mutateAsync({ email, password });
      navigate("/", { replace: true });
    } catch {
      // error surfaced via login.error below
    }
  }

  return (
    <form className="auth-page" onSubmit={handleSubmit}>
      <h1>Log in</h1>
      <label>
        Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label>
        Password
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </label>
      {login.error && <p role="alert">{login.error instanceof ApiError ? login.error.message : "Login failed"}</p>}
      <button type="submit" disabled={login.isPending}>
        {login.isPending ? "Logging in…" : "Log in"}
      </button>
      <p>
        No account? <a href="/signup">Sign up</a>
      </p>
    </form>
  );
}
