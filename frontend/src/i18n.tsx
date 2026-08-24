import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { translations } from "./translations";

export type Lang = "fr" | "en" | "es";

export const LANGS: Lang[] = ["fr", "en", "es"];
export const LANG_LABELS: Record<Lang, string> = { fr: "FR", en: "EN", es: "ES" };
export const LANG_NAMES: Record<Lang, string> = {
  fr: "Français",
  en: "English",
  es: "Español",
};

const DEFAULT_LANG: Lang = "fr";
const STORAGE_KEY = "gigpipeline.lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && (LANGS as string[]).includes(saved)) {
      return saved as Lang;
    }
  } catch {
    /* private mode / blocked storage — fall back to the default */
  }
  return DEFAULT_LANG;
}

type Vars = Record<string, string | number>;

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Vars) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore — the choice just won't persist across reloads */
    }
  }, []);

  useEffect(() => {
    try {
      document.documentElement.lang = lang;
    } catch {
      /* non-browser context */
    }
  }, [lang]);

  const t = useCallback(
    (key: string, vars?: Vars) => {
      const dict = translations[lang] ?? translations[DEFAULT_LANG];
      let str = dict[key] ?? translations[DEFAULT_LANG][key] ?? key;
      if (vars) {
        for (const [name, value] of Object.entries(vars)) {
          str = str.split(`{${name}}`).join(String(value));
        }
      }
      return str;
    },
    [lang],
  );

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return ctx;
}

export function useT(): (key: string, vars?: Vars) => string {
  return useI18n().t;
}
