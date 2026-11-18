export interface TranslationBundle {
  locale: string;
  namespace: string;
  messages: Record<string, string>;
}

export interface LoaderOptions {
  baseUrl: string;
  fetcher?: typeof fetch;
  fallbackLocale?: string;
}

interface CacheEntry {
  etag: string | null;
  bundle: TranslationBundle;
}

/**
 * Runtime translation loader. Bundles come from the school API so edits made in
 * the Translation Editor appear without a redeploy (ARCH §5.6). ETags avoid
 * re-downloading unchanged namespaces.
 */
export class TranslationLoader {
  private cache = new Map<string, CacheEntry>();
  private fetcher: typeof fetch;

  constructor(private options: LoaderOptions) {
    // Browsers require `fetch` to be called with `window` as the receiver; a
    // bare `this.fetcher(...)` throws "Illegal invocation", so bind it.
    this.fetcher = options.fetcher ?? globalThis.fetch.bind(globalThis);
  }

  private key(locale: string, namespace: string) {
    return `${locale}:${namespace}`;
  }

  async load(locale: string, namespace: string): Promise<TranslationBundle> {
    const key = this.key(locale, namespace);
    const cached = this.cache.get(key);
    const headers: Record<string, string> = { Accept: "application/json" };
    if (cached?.etag) headers["If-None-Match"] = cached.etag;
    const response = await this.fetcher(
      `${this.options.baseUrl.replace(/\/$/, "")}/api/v1/i18n/${locale}/${namespace}`,
      { headers },
    );
    if (response.status === 304 && cached) return cached.bundle;
    if (!response.ok) {
      if (cached) return cached.bundle;
      const fallback = this.options.fallbackLocale ?? "en";
      if (locale !== fallback) return this.load(fallback, namespace);
      throw new Error(`Cannot load translations ${locale}/${namespace}`);
    }
    const bundle = (await response.json()) as TranslationBundle;
    this.cache.set(key, { etag: response.headers.get("etag"), bundle });
    return bundle;
  }

  async loadMany(locale: string, namespaces: string[]): Promise<Record<string, string>> {
    // A disabled module refuses its own namespace (403); that must not blank out
    // every other bundle, so failed namespaces are skipped.
    const results = await Promise.allSettled(namespaces.map((namespace) => this.load(locale, namespace)));
    const bundles = results
      .filter((result): result is PromiseFulfilledResult<TranslationBundle> => result.status === "fulfilled")
      .map((result) => result.value);
    if (bundles.length === 0 && results.length > 0) {
      const first = results.find((result) => result.status === "rejected");
      throw first && first.status === "rejected" ? first.reason : new Error("No translations loaded");
    }
    return bundles.reduce<Record<string, string>>((messages, bundle) => {
      // Later namespaces do not override earlier ones silently; namespaces are
      // expected to use distinct prefixes. Core is loaded first by convention.
      // Module bundles ship bare keys ("nav", "perm.view"); manifests address
      // them as "academics.nav", so prefix them here once, at load time.
      if (bundle.namespace === "core") {
        return { ...bundle.messages, ...messages };
      }
      const prefixed = Object.fromEntries(
        Object.entries(bundle.messages).map(([key, value]) => [
          `${bundle.namespace}.${key}`,
          value,
        ]),
      );
      return { ...prefixed, ...messages };
    }, {});
  }

  clear(): void {
    this.cache.clear();
  }

  peek(locale: string, namespace: string): TranslationBundle | undefined {
    return this.cache.get(this.key(locale, namespace))?.bundle;
  }
}

export function interpolate(template: string, values: Record<string, string | number> = {}): string {
  return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, key) =>
    Object.prototype.hasOwnProperty.call(values, key) ? String(values[key]) : match,
  );
}

export function translator(messages: Record<string, string>) {
  return (key: string, values?: Record<string, string | number>) =>
    interpolate(messages[key] ?? key, values);
}
