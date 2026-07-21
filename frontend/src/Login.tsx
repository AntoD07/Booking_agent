import { FormEvent, useState } from "react";
import { login } from "./api";
import "./Login.css";

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Wrong password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <div className="login-card">
        <p className="login-overline">Gig Pipeline</p>
        <h1 className="login-title">The 2027 season awaits.</h1>
        <form onSubmit={submit} className="login-form">
          <label className="login-label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoFocus
            required
          />
          <button type="submit" disabled={busy}>
            {busy ? "Opening…" : "Enter"}
          </button>
          {error && <p className="login-error">{error}</p>}
        </form>
      </div>
    </main>
  );
}
