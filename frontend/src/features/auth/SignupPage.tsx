import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useSignup } from "./useAuth";

export function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const signup = useSignup();
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await signup.mutateAsync({ email, password, display_name: displayName });
      navigate("/", { replace: true });
    } catch {
      // error surfaced via signup.error below
    }
  }

  return (
    <form className="auth-page" onSubmit={handleSubmit}>
      <h1>Create your account</h1>
      <p>No club or invite needed — you'll be able to self-report transponder usage right away.</p>
      <label>
        Display name
        <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
      </label>
      <label>
        Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label>
        Password
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </label>
      {signup.error && (
        <p role="alert">{signup.error instanceof ApiError ? signup.error.message : "Signup failed"}</p>
      )}
      <button type="submit" disabled={signup.isPending}>
        {signup.isPending ? "Creating account…" : "Sign up"}
      </button>
      <p>
        Already have an account? <a href="/login">Log in</a>
      </p>
    </form>
  );
}
