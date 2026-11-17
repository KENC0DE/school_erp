import { TranslationLoader, translator } from "@erp/i18n";
import { useCallback, useEffect, useState } from "react";

import type { VerifiedProfile } from "../directory/types";
import { forSchool, getVerifiedBaseUrl } from "../storage/schoolStorage";
import type { Locale } from "./ui-messages";

const NAMESPACES = ["core", "sample"] as const;

interface CachedBundle {
  messages?: Record<string, string>;
}

export interface SchoolTranslations {
  t: (key: string, values?: Record<string, string | number>) => string;
  ready: boolean;
  reload: () => void;
}

/**
 * Loads core + module translations from the selected school and caches each
 * namespace in that school's secure-store namespace. A failed refresh keeps the
 * cached copy; a failed first load leaves keys visible rather than crashing.
 */
export function useSchoolTranslations(
  profile: VerifiedProfile | null,
  locale: Locale,
): SchoolTranslations {
  const [messages, setMessages] = useState<Record<string, string>>({});
  const [ready, setReady] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!profile) return;
    let cancelled = false;
    const store = forSchool(profile.instanceId);
    setReady(false);

    async function loadCached(): Promise<Record<string, string>> {
      const merged: Record<string, string> = {};
      for (const namespace of [...NAMESPACES].reverse()) {
        const bundle = await store.getCache<CachedBundle>(`i18n.${locale}.${namespace}`);
        if (bundle?.messages) Object.assign(merged, bundle.messages);
      }
      return merged;
    }

    async function run(): Promise<void> {
      const cached = await loadCached();
      if (!cancelled && Object.keys(cached).length > 0) {
        setMessages(cached);
        setReady(true);
      }
      try {
        const baseUrl = await getVerifiedBaseUrl(profile!.instanceId);
        const loader = new TranslationLoader({ baseUrl });
        const bundles = await Promise.all(
          NAMESPACES.map((namespace) => loader.load(locale, namespace)),
        );
        const merged: Record<string, string> = {};
        for (const bundle of [...bundles].reverse()) Object.assign(merged, bundle.messages);
        if (!cancelled) {
          setMessages(merged);
          setReady(true);
        }
        await Promise.all(
          bundles.map((bundle) =>
            store.setCache(`i18n.${bundle.locale}.${bundle.namespace}`, bundle),
          ),
        );
      } catch {
        if (!cancelled) setReady(true);
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [profile?.instanceId, locale, version]);

  const t = useCallback(
    (key: string, values?: Record<string, string | number>) => translator(messages)(key, values),
    [messages],
  );

  return {
    t,
    ready,
    reload: () => setVersion((current) => current + 1),
  };
}
