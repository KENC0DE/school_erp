import { TranslationLoader } from "@erp/i18n";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { API_URL } from "../lib/api";
import { getStoredLocale, storeLocale } from "../lib/storage";

const NAMESPACES = ["core", "sample", "academics", "students", "admissions"];

interface I18nState {
  locale: string;
  languages: string[];
  ready: boolean;
  t: (key: string, values?: Record<string, string | number>) => string;
  setLocale: (locale: string) => void;
  reload: () => void;
}

const I18nContext = createContext<I18nState | null>(null);

export function I18nProvider({
  children,
  initialMessages,
}: {
  children: ReactNode;
  initialMessages?: Record<string, string>;
}) {
  const [locale, setLocaleState] = useState(getStoredLocale());
  const [messages, setMessages] = useState<Record<string, string>>(initialMessages ?? {});
  const [ready, setReady] = useState(Boolean(initialMessages));
  const loader = useMemo(() => new TranslationLoader({ baseUrl: API_URL }), []);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (initialMessages) return;
    let cancelled = false;
    setReady(false);
    loader
      .loadMany(locale, NAMESPACES)
      .then((loaded) => {
        if (!cancelled) {
          setMessages(loaded);
          setReady(true);
        }
      })
      .catch(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [locale, loader, initialMessages, version]);

  const setLocale = useCallback((next: string) => {
    setLocaleState(next);
    storeLocale(next);
  }, []);

  const t = useCallback(
    (key: string, values?: Record<string, string | number>) => {
      const template = messages[key] ?? key;
      if (!values) return template;
      return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, name) =>
        Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match,
      );
    },
    [messages],
  );

  const value = useMemo(
    () => ({
      locale,
      languages: ["en", "am"],
      ready,
      t,
      setLocale,
      reload: () => setVersion((current) => current + 1),
    }),
    [locale, ready, t, setLocale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used inside I18nProvider");
  return context;
}
