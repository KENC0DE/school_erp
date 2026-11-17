import { useCallback, useEffect, useState } from "react";

import type { VerifiedProfile } from "../directory/types";
import { fetchNavigation, type Navigation } from "../session/session";
import { forSchool } from "../storage/schoolStorage";

export function useSchoolNavigation(profile: VerifiedProfile | null) {
  const [navigation, setNavigation] = useState<Navigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    setError(null);
    const store = forSchool(profile.instanceId);
    const cached = await store.getCache<Navigation>("navigation");
    if (cached?.items) setNavigation(cached);
    try {
      const fresh = await fetchNavigation(profile.instanceId);
      setNavigation(fresh);
      await store.setCache("navigation", fresh);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "UNKNOWN");
    } finally {
      setLoading(false);
    }
  }, [profile?.instanceId]);

  useEffect(() => {
    void load();
  }, [load]);

  return { navigation, loading, error, reload: load };
}
