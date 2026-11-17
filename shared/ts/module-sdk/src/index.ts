export interface ModuleNavItem {
  key: string;
  labelKey: string;
  path: string;
  icon?: string;
  permission?: string;
  order?: number;
}

export interface ModuleRoute {
  path: string;
  permission?: string;
  /** A lazy component loader so the shell can code-split per module. */
  component: () => Promise<{ default: unknown }>;
}

export interface ModuleScreen {
  key: string;
  titleKey: string;
  component: () => Promise<{ default: unknown }>;
}

export interface FrontendModuleManifest {
  key: string;
  name: string;
  version: string;
  nav: ModuleNavItem[];
  routes: ModuleRoute[];
  mobileScreens?: ModuleScreen[];
}

export class ModuleRegistry {
  private modules = new Map<string, FrontendModuleManifest>();

  register(manifest: FrontendModuleManifest): void {
    if (this.modules.has(manifest.key)) {
      throw new Error(`Duplicate frontend module '${manifest.key}'`);
    }
    this.modules.set(manifest.key, manifest);
  }

  get(key: string): FrontendModuleManifest | undefined {
    return this.modules.get(key);
  }

  all(): FrontendModuleManifest[] {
    return [...this.modules.values()].sort((a, b) => a.key.localeCompare(b.key));
  }

  /** Navigation is server-driven; this only decorates server items with routes. */
  navFor(enabledModules: string[], permitted: Set<string>): Array<ModuleNavItem & { module: string }> {
    const enabled = new Set(enabledModules);
    return this.all()
      .filter((manifest) => enabled.has(manifest.key))
      .flatMap((manifest) =>
        manifest.nav
          .filter((item) => !item.permission || permitted.has(item.permission))
          .map((item) => ({ ...item, module: manifest.key })),
      )
      .sort((a, b) => (a.order ?? 100) - (b.order ?? 100));
  }
}

export const moduleRegistry = new ModuleRegistry();
