import { FormEvent, useState } from "react";
import { login, registerBand } from "./api";
import { useT } from "./i18n";
import LangSwitcher from "./LangSwitcher";
import "./Login.css";

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const t = useT();
  const [mode, setMode] = useState<"login" | "register">("login");

  return (
    <main className="login">
      <div className="login-card">
        <p className="login-overline">{t("login.overline")}</p>
        <h1 className="login-title">{t("login.title")}</h1>
        {mode === "login" ? (
          <SignInForm onSuccess={onSuccess} onRegister={() => setMode("register")} />
        ) : (
          <RegisterForm onBack={() => setMode("login")} />
        )}
        <div className="login-lang">
          <LangSwitcher />
        </div>
      </div>
    </main>
  );
}

function SignInForm({
  onSuccess,
  onRegister,
}: {
  onSuccess: () => void;
  onRegister: () => void;
}) {
  const t = useT();
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
        err instanceof Error && err.message ? err.message : t("login.error"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="login-form">
      <label className="login-label" htmlFor="band">
        {t("login.band")}
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
        {t("login.password")}
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
        {busy ? t("login.opening") : t("login.enter")}
      </button>
      {error && <p className="login-error">{error}</p>}
      <button type="button" className="login-linkish" onClick={onRegister}>
        {t("login.registerLink")}
      </button>
    </form>
  );
}

function RegisterForm({ onBack }: { onBack: () => void }) {
  const t = useT();
  const [adminPassword, setAdminPassword] = useState("");
  const [bandName, setBandName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await registerBand(adminPassword, bandName, password);
      setNotice(
        t(result.created ? "register.created" : "register.updated", {
          name: result.band_name,
        }),
      );
      setBandName("");
      setPassword("");
    } catch (err) {
      setError(
        err instanceof Error && err.message ? err.message : t("register.error"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="login-form">
      <p className="login-subtitle">{t("register.subtitle")}</p>
      <label className="login-label" htmlFor="admin">
        {t("register.adminPassword")}
      </label>
      <input
        id="admin"
        type="password"
        value={adminPassword}
        onChange={(event) => setAdminPassword(event.target.value)}
        autoFocus
        required
      />
      <label className="login-label" htmlFor="newband">
        {t("register.bandName")}
      </label>
      <input
        id="newband"
        type="text"
        value={bandName}
        onChange={(event) => setBandName(event.target.value)}
        required
      />
      <label className="login-label" htmlFor="newpass">
        {t("register.bandPassword")}
      </label>
      <input
        id="newpass"
        type="text"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        required
      />
      <button type="submit" disabled={busy}>
        {busy ? t("register.creating") : t("register.create")}
      </button>
      {notice && <p className="login-notice">{notice}</p>}
      {error && <p className="login-error">{error}</p>}
      <button type="button" className="login-linkish" onClick={onBack}>
        {t("login.backToLogin")}
      </button>
    </form>
  );
}
