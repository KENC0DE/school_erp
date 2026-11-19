import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { api, type LoginResult } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";

const LANGUAGES = ["en", "am"];
const CALENDARS = ["ethiopian", "gregorian", "both"];
const LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"];
const DEFAULT_MAX_LOGO_BYTES = 25_000_000;

interface SetupSchool {
  name: string;
  timezone: string;
  calendar: string;
  default_language: string;
  enabled_languages: string[];
  first_level: number;
  last_level: number;
  theme: string;
  logo_url: string | null;
}

interface SetupStatus {
  required: boolean;
  completed: boolean;
  school: SetupSchool;
  languages: string[];
  calendars: string[];
  themes: { key: string; name: string; is_default: boolean }[];
  limits: { logo_max_bytes: number };
}

interface SetupResult {
  tokens: LoginResult["tokens"];
  user: LoginResult["user"];
  school: Record<string, unknown>;
  logo_url: string | null;
  theme: string;
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("read failed"));
    reader.readAsDataURL(file);
  });
}

function passwordProblem(value: string): boolean {
  return value.length < 12 || !/[A-Za-z]/.test(value) || !/[0-9]/.test(value);
}

export function SetupWizardPage() {
  const { t } = useI18n();
  const { adoptSession } = useAuth();
  const navigate = useNavigate();

  const status = useQuery({
    queryKey: ["setup-status"],
    queryFn: () => api.get<SetupStatus>("/api/v1/setup/status"),
    retry: false,
  });

  const [schoolName, setSchoolName] = useState("");
  const [timezone, setTimezone] = useState("Africa/Addis_Ababa");
  const [calendar, setCalendar] = useState("both");
  const [defaultLanguage, setDefaultLanguage] = useState("en");
  const [enabledLanguages, setEnabledLanguages] = useState<string[]>(["en", "am"]);
  const [firstLevel, setFirstLevel] = useState(0);
  const [lastLevel, setLastLevel] = useState(12);
  const [theme, setTheme] = useState("default");
  const [logo, setLogo] = useState<string | null>(null);
  const [logoError, setLogoError] = useState<string | null>(null);
  const [adminName, setAdminName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminPhone, setAdminPhone] = useState("");
  const [error, setError] = useState<string | null>(null);

  const maxLogoBytes = status.data?.limits.logo_max_bytes ?? DEFAULT_MAX_LOGO_BYTES;

  useEffect(() => {
    const school = status.data?.school;
    if (!school) return;
    setSchoolName(school.name ?? "");
    setTimezone(school.timezone ?? "Africa/Addis_Ababa");
    setCalendar(school.calendar ?? "both");
    setDefaultLanguage(school.default_language ?? "en");
    setEnabledLanguages(school.enabled_languages ?? ["en", "am"]);
    setFirstLevel(school.first_level ?? 0);
    setLastLevel(school.last_level ?? 12);
    setTheme(school.theme ?? "default");
  }, [status.data]);

  const submit = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post<SetupResult>("/api/v1/setup", body),
    onSuccess: (result) => {
      adoptSession({ tokens: result.tokens, user: result.user });
      navigate("/", { replace: true });
    },
    onError: (err) => {
      setError(err instanceof ApiRequestError ? err.message : t("setup.error"));
    },
  });

  function toggleLanguage(code: string, checked: boolean) {
    setEnabledLanguages((current) => {
      if (checked) return current.includes(code) ? current : [...current, code];
      return current.filter((item) => item !== code);
    });
  }

  async function chooseLogo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setLogoError(null);
    if (!file) {
      setLogo(null);
      return;
    }
    if (!LOGO_TYPES.includes(file.type)) {
      setLogoError(t("error.setup_logo"));
      setLogo(null);
      return;
    }
    if (file.size > maxLogoBytes) {
      setLogoError(
        t("files.error.too_large", { max: Math.round(maxLogoBytes / 1_000_000) }),
      );
      setLogo(null);
      return;
    }
    try {
      setLogo(await readAsDataUrl(file));
    } catch {
      setLogoError(t("setup.error"));
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!enabledLanguages.includes(defaultLanguage)) {
      setError(t("error.setup_language"));
      return;
    }
    if (firstLevel > lastLevel) {
      setError(t("error.setup_grade_scope"));
      return;
    }
    if (passwordProblem(adminPassword)) {
      setError(t("setup.admin_password_hint"));
      return;
    }
    submit.mutate({
      school: {
        name: schoolName,
        timezone,
        calendar,
        default_language: defaultLanguage,
        enabled_languages: enabledLanguages,
        first_level: firstLevel,
        last_level: lastLevel,
        theme,
        logo,
      },
      admin: {
        email: adminEmail,
        password: adminPassword,
        display_name: adminName,
        phone: adminPhone.trim() || null,
        locale: defaultLanguage,
      },
    });
  }

  if (status.isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background p-4">
        <p className="text-sm text-muted-foreground">{t("setup.loading")}</p>
      </main>
    );
  }

  if (status.isError || !status.data) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardContent className="space-y-3 pt-5">
            <p className="text-sm text-destructive">{t("common.error")}</p>
            <Button variant="outline" onClick={() => status.refetch()}>
              {t("common.retry")}
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (status.data.completed) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>{t("setup.complete_title")}</CardTitle>
            <CardDescription>{t("setup.complete_body")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              className="text-sm font-medium text-primary underline-offset-4 hover:underline"
              to="/login"
            >
              {t("setup.go_to_login")}
            </Link>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-start justify-center bg-background p-4 py-10">
      <Card className="w-full max-w-3xl">
        <CardHeader>
          <CardTitle>{t("setup.title")}</CardTitle>
          <CardDescription>{t("setup.intro")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-8" onSubmit={onSubmit} data-testid="setup-form">
            <section className="space-y-4">
              <h2 className="text-lg font-semibold">{t("setup.school_section")}</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5 sm:col-span-2">
                  <label htmlFor="school-name" className="text-sm font-medium">
                    {t("setup.school_name")}
                  </label>
                  <Input
                    id="school-name"
                    required
                    value={schoolName}
                    onChange={(event) => setSchoolName(event.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="timezone" className="text-sm font-medium">
                    {t("setup.timezone")}
                  </label>
                  <Input
                    id="timezone"
                    required
                    value={timezone}
                    onChange={(event) => setTimezone(event.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="calendar" className="text-sm font-medium">
                    {t("setup.calendar")}
                  </label>
                  <select
                    id="calendar"
                    className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={calendar}
                    onChange={(event) => setCalendar(event.target.value)}
                  >
                    {(status.data.calendars.length ? status.data.calendars : CALENDARS).map(
                      (option) => (
                        <option key={option} value={option}>
                          {t(`settings.enum.${option}`)}
                        </option>
                      ),
                    )}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="default-language" className="text-sm font-medium">
                    {t("setup.default_language")}
                  </label>
                  <select
                    id="default-language"
                    className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={defaultLanguage}
                    onChange={(event) => setDefaultLanguage(event.target.value)}
                  >
                    {(status.data.languages.length ? status.data.languages : LANGUAGES).map(
                      (option) => (
                        <option key={option} value={option}>
                          {t(`settings.enum.${option}`)}
                        </option>
                      ),
                    )}
                  </select>
                </div>
                <fieldset className="space-y-1.5">
                  <legend className="text-sm font-medium">{t("setup.enabled_languages")}</legend>
                  <div className="flex items-center gap-4 py-2">
                    {(status.data.languages.length ? status.data.languages : LANGUAGES).map(
                      (option) => (
                        <label key={option} className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            aria-label={t(`settings.enum.${option}`)}
                            checked={enabledLanguages.includes(option)}
                            onChange={(event) => toggleLanguage(option, event.target.checked)}
                          />
                          <span>{t(`settings.enum.${option}`)}</span>
                        </label>
                      ),
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t("setup.enabled_languages_hint")}
                  </p>
                </fieldset>
                <div className="space-y-1.5">
                  <label htmlFor="first-level" className="text-sm font-medium">
                    {t("setup.first_level")}
                  </label>
                  <Input
                    id="first-level"
                    type="number"
                    min={0}
                    max={12}
                    value={firstLevel}
                    onChange={(event) => setFirstLevel(Number(event.target.value))}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="last-level" className="text-sm font-medium">
                    {t("setup.last_level")}
                  </label>
                  <Input
                    id="last-level"
                    type="number"
                    min={0}
                    max={12}
                    value={lastLevel}
                    onChange={(event) => setLastLevel(Number(event.target.value))}
                  />
                </div>
                <div className="space-y-1.5 sm:col-span-2">
                  <p className="text-xs text-muted-foreground">{t("setup.grade_scope_hint")}</p>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="theme" className="text-sm font-medium">
                    {t("setup.theme")}
                  </label>
                  <select
                    id="theme"
                    className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={theme}
                    onChange={(event) => setTheme(event.target.value)}
                  >
                    {status.data.themes.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="logo" className="text-sm font-medium">
                    {t("setup.logo")}
                  </label>
                  <input
                    id="logo"
                    type="file"
                    accept={LOGO_TYPES.join(",")}
                    className="block w-full text-sm"
                    onChange={chooseLogo}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t("setup.logo_hint", {
                      max: Math.round(maxLogoBytes / 1_000_000),
                    })}
                  </p>
                  {logoError ? (
                    <p role="alert" className="text-sm text-destructive">
                      {logoError}
                    </p>
                  ) : null}
                  {logo ? (
                    <div className="flex items-center gap-3">
                      <img
                        src={logo}
                        alt={t("setup.logo")}
                        width={64}
                        height={64}
                        className="h-16 w-16 rounded-md border object-contain"
                      />
                      <Button type="button" variant="outline" onClick={() => setLogo(null)}>
                        {t("setup.logo_remove")}
                      </Button>
                    </div>
                  ) : null}
                </div>
              </div>
            </section>

            <section className="space-y-4 border-t pt-6">
              <h2 className="text-lg font-semibold">{t("setup.admin_section")}</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label htmlFor="admin-name" className="text-sm font-medium">
                    {t("setup.admin_name")}
                  </label>
                  <Input
                    id="admin-name"
                    required
                    value={adminName}
                    onChange={(event) => setAdminName(event.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="admin-email" className="text-sm font-medium">
                    {t("setup.admin_email")}
                  </label>
                  <Input
                    id="admin-email"
                    type="email"
                    autoComplete="username"
                    required
                    value={adminEmail}
                    onChange={(event) => setAdminEmail(event.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="admin-password" className="text-sm font-medium">
                    {t("setup.admin_password")}
                  </label>
                  <Input
                    id="admin-password"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={adminPassword}
                    onChange={(event) => setAdminPassword(event.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t("setup.admin_password_hint")}
                  </p>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="admin-phone" className="text-sm font-medium">
                    {t("setup.admin_phone")}
                  </label>
                  <Input
                    id="admin-phone"
                    value={adminPhone}
                    onChange={(event) => setAdminPhone(event.target.value)}
                  />
                </div>
              </div>
            </section>

            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}

            <Button type="submit" disabled={submit.isPending}>
              {submit.isPending ? t("setup.submitting") : t("setup.submit")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
