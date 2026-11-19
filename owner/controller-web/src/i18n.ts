import { interpolate } from "@erp/i18n";
import { useCallback } from "react";

/**
 * Every visible string in the controller web app lives here. Keys follow
 * `controller.<area>.<name>` so a future API-backed translation bundle can be
 * dropped in without touching components.
 */
export const MESSAGES = {
  "controller.app.title": "School ERP Controller",
  "controller.app.brand": "School ERP",
  "controller.app.brandSuffix": "Control Plane",
  "controller.nav.label": "Controller navigation",
  "controller.nav.schools": "Schools",
  "controller.nav.vault": "Audit Vault",
  "controller.header.themeToDark": "Switch to dark theme",
  "controller.header.themeToLight": "Switch to light theme",
  "controller.header.logout": "Log out",
  "controller.role.owner": "Platform Owner",
  "controller.role.support": "Controller Support",
  "controller.role.unknown": "Controller user",

  "controller.login.title": "Controller sign in",
  "controller.login.subtitle": "Sign in with your platform owner or support account.",
  "controller.login.email": "Email",
  "controller.login.password": "Password",
  "controller.login.submit": "Sign in",
  "controller.login.submitting": "Signing in…",
  "controller.login.invalid": "Email or password is incorrect",

  "controller.schools.title": "Schools",
  "controller.schools.description": "Every school instance enrolled with this controller.",
  "controller.schools.empty": "No schools are enrolled yet.",
  "controller.schools.modules": "{{count}} modules",
  "controller.schools.modulesOne": "{{count}} module",
  "controller.schools.enrolled": "Enrolled",
  "controller.schools.notEnrolled": "Not enrolled",
  "controller.schools.status.active": "Active",
  "controller.schools.status.grace": "Grace period",
  "controller.schools.status.suspended": "Suspended",
  "controller.schools.status.unknown": "Unknown status",

  "controller.school.back": "Back to schools",
  "controller.school.details": "School details",
  "controller.school.code": "School code",
  "controller.school.apiUrl": "API base URL",
  "controller.school.plan": "Plan",
  "controller.school.appVersion": "App version",
  "controller.school.enrollment": "Enrollment",
  "controller.school.modules.title": "Licensed modules",
  "controller.school.modules.description": "Turn optional modules on or off for this school.",
  "controller.school.modules.enabled": "On",
  "controller.school.modules.disabled": "Off",
  "controller.school.modules.toggleLabel": "{{module}} module",
  "controller.school.modules.error": "Could not update the module. Try again.",
  "controller.school.openAsAdmin": "Open as school admin",
  "controller.school.openAsAdminHint":
    "Opens a short-lived, audited session in the school web app. A reason is required.",

  "controller.support.title": "Open as school admin",
  "controller.support.description":
    "This creates an audited support session for {{school}}. Actions taken in the school will be recorded as controller actions.",
  "controller.support.reason": "Reason for access",
  "controller.support.reasonHint": "At least 4 characters, up to 1000.",
  "controller.support.tooShort": "Enter at least 4 characters.",
  "controller.support.submit": "Open support session",
  "controller.support.submitting": "Opening…",
  "controller.support.cancel": "Cancel",
  "controller.support.close": "Close",
  "controller.support.success": "Support session created. The school opened in a new tab.",
  "controller.support.token": "Session token",
  "controller.support.expires": "Expires at",
  "controller.support.error": "Could not open a support session.",

  "controller.vault.title": "Audit Vault",
  "controller.vault.description": "Hash-chained audit entries shipped by school instances.",
  "controller.vault.schoolFilter": "School",
  "controller.vault.allSchools": "All schools",
  "controller.vault.limit": "Showing the latest {{count}} entries.",
  "controller.vault.empty": "No audit entries match this filter.",
  "controller.vault.column.school": "School",
  "controller.vault.column.seq": "Seq",
  "controller.vault.column.action": "Action",
  "controller.vault.column.module": "Module",
  "controller.vault.column.actor": "Actor",
  "controller.vault.column.via": "Via",
  "controller.vault.viaValue": "via={{via}}",
  "controller.vault.column.entity": "Entity",
  "controller.vault.column.time": "Time",
  "controller.vault.column.chain": "Chain",
  "controller.vault.chain.ok": "Verified",
  "controller.vault.chain.broken": "Broken chain",
  "controller.vault.chain.any": "Any chain state",
  "controller.vault.chain": "Chain state",
  "controller.vault.search": "Search",
  "controller.vault.searchPlaceholder": "Action, entity or actor",
  "controller.vault.apply": "Apply",
  "controller.vault.health": "Chain health",
  "controller.vault.scan": "Scan for anomalies",
  "controller.vault.scanning": "Scanning…",
  "controller.vault.noAlerts": "No open alerts.",
  "controller.vault.statusLine": "{{entries}} entries · head seq {{lastSeq}} · {{broken}} broken",

  "controller.common.loading": "Loading…",
  "controller.common.error": "Something went wrong.",
  "controller.common.retry": "Retry",
  "controller.common.none": "—",
} as const satisfies Record<string, string>;

export type Messages = typeof MESSAGES;
export type MessageKey = keyof Messages;

export type Translate = (key: MessageKey, values?: Record<string, string | number>) => string;

/** Typed English translator. Kept as a hook so a locale provider can slot in later. */
export function useT(): Translate {
  return useCallback((key: MessageKey, values?: Record<string, string | number>) => {
    return interpolate(MESSAGES[key], values);
  }, []);
}

const STATUS_KEYS = {
  active: "controller.schools.status.active",
  grace: "controller.schools.status.grace",
  suspended: "controller.schools.status.suspended",
} as const satisfies Record<string, MessageKey>;

export function statusMessageKey(status: string): MessageKey {
  return STATUS_KEYS[status as keyof typeof STATUS_KEYS] ?? "controller.schools.status.unknown";
}

const ROLE_KEYS = {
  owner: "controller.role.owner",
  support: "controller.role.support",
} as const satisfies Record<string, MessageKey>;

export function roleMessageKey(role: string): MessageKey {
  return ROLE_KEYS[role as keyof typeof ROLE_KEYS] ?? "controller.role.unknown";
}
