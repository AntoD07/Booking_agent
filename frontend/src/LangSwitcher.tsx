import { LANGS, LANG_LABELS, useI18n } from "./i18n";
import "./LangSwitcher.css";

/** A compact FR / EN / ES toggle. Used on the login screen and the board. */
export default function LangSwitcher() {
  const { lang, setLang, t } = useI18n();
  return (
    <div className="lang-switcher" role="group" aria-label={t("lang.label")}>
      {LANGS.map((code) => (
        <button
          key={code}
          type="button"
          className={`lang-option${code === lang ? " lang-option--active" : ""}`}
          aria-pressed={code === lang}
          onClick={() => setLang(code)}
        >
          {LANG_LABELS[code]}
        </button>
      ))}
    </div>
  );
}
