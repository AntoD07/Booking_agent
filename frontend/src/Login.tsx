import { FormEvent, useState } from "react";
import { login } from "./api";
import "./Login.css";

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const [bandName, setBandName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(bandName, password);
      onSuccess();
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : "Wrong band name or password",
      );
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
          <label className="login-label" htmlFor="band">
            Band
          </label>
          <input
            id="band"
            type="text"
            value={bandName}
            onChange={(event) => setBandName(event.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
          <label className="login-label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
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
