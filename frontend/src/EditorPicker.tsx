import { FormEvent, useEffect, useState } from "react";
import { fetchEditors, setEditor as apiSetEditor } from "./api";
import { useT } from "./i18n";
import LangSwitcher from "./LangSwitcher";
import "./Login.css";

export const EDITOR_STORAGE_KEY = "gigpipeline.editor";

/** Shown once after login (unless a name is remembered): pick which bandmate
 * you are, so your edits are attributed. The choice is stored on the session
 * cookie and remembered per device, so it isn't asked again. */
export default function EditorPicker({
  bandName,
  onPicked,
}: {
  bandName: string;
  onPicked: (editor: string) => void;
}) {
  const t = useT();
  const [members, setMembers] = useState<string[]>([]);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEditors()
      .then(setMembers)
      .catch(() => setMembers([]));
  }, []);

  async function choose(name: string) {
    const value = name.trim();
    if (!value) return;
    setBusy(true);
    setError(null);
    try {
      await apiSetEditor(value);
      try {
        localStorage.setItem(EDITOR_STORAGE_KEY, value);
      } catch {
        /* ignore blocked storage */
      }
      onPicked(value);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : t("editor.error"));
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    choose(typed);
  }

  return (
    <main className="login">
      <div className="login-card">
        <p className="login-overline">{bandName}</p>
        <h1 className="login-title">{t("editor.title")}</h1>
        {members.length > 0 && (
          <div className="editor-members">
            {members.map((name) => (
              <button
                key={name}
                type="button"
                className="editor-member"
                disabled={busy}
                onClick={() => choose(name)}
              >
                {name}
              </button>
            ))}
          </div>
        )}
        <form onSubmit={submit} className="login-form">
          <label className="login-label" htmlFor="editor-name">
            {members.length > 0 ? t("editor.orType") : t("editor.yourName")}
          </label>
          <input
            id="editor-name"
            type="text"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            autoComplete="off"
          />
          <button type="submit" disabled={busy || !typed.trim()}>
            {busy ? t("editor.saving") : t("editor.continue")}
          </button>
          {error && <p className="login-error">{error}</p>}
        </form>
        <div className="login-lang">
          <LangSwitcher />
        </div>
      </div>
    </main>
  );
}
