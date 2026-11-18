# Decisions

Ambiguities are resolved with the simplest option consistent with the architecture
and recorded here (date, decision, reason).

## 2026-11-17 — Python/Node tooling and database fallback

- **Decision:** Production targets PostgreSQL 16+ (compose), but the app accepts any
  SQLAlchemy async URL. Automated tests and the local dev fallback use SQLite
  (`sqlite+aiosqlite`) because this build host has no Docker daemon and no
  PostgreSQL binaries installed.
- **Reason:** The build guide's verify steps must run here. All schema uses portable
  SQLAlchemy types (`Uuid`, `JSON` with a JSONB variant on PostgreSQL), so switching
  to PostgreSQL is a connection-string change plus `alembic upgrade heads`.
- **Consequences:** `pg_trgm`, `FOR UPDATE` row locks and column-level `REVOKE` are
  PostgreSQL-only; migrations apply them conditionally. The hash chain is guarded
  by SQLite triggers locally and by REVOKE on PostgreSQL.

## 2026-11-17 — Python 3.14 runtime, 3.12 minimum

- **Decision:** `requires-python = ">=3.12"`; this host runs 3.14.
- **Reason:** Architecture says 3.12+; no 3.12-specific code is used.

## 2026-11-17 — Auth tokens

- **Decision:** Access tokens are HS256 JWTs (15 min). Refresh tokens are opaque
  256-bit values stored as SHA-256 hashes, rotated on every use, with reuse detection
  that revokes the whole token family.
- **Reason:** Simpler than a second signing key and gives real rotation semantics.
  Web uses the same bearer flow behind the SPA; httpOnly cookie + CSRF hardening is
  scheduled for P1-04.

## 2026-11-17 — Licensing

- **Decision:** Licenses are EdDSA (Ed25519) JWTs signed by the controller and verified
  offline with the controller public key. When no license is stored (fresh dev
  instance), all modules are treated as licensed; once a license exists its module
  list is authoritative.
- **Reason:** Keeps a clean-clone demo bootable without a running controller while
  still exercising the real gate as soon as enrollment happens.

## 2026-11-17 — Audit chain storage

- **Decision:** `audit_log.seq` is a monotonically increasing integer primary key; the
  hash covers the canonical JSON of the entry plus `prev_hash`. The app role gets no
  UPDATE/DELETE (PostgreSQL) and triggers block them (SQLite).
- **Reason:** Simple, verifiable, portable.

## 2026-11-17 — PDF renderer decision (P0-23)

- **Decision:** **Playwright/Chromium** is the primary renderer, with a ReportLab
  fallback used when Chromium is unavailable on the host.
- **Findings:** Chromium handles Ethiopic shaping, font embedding and complex CSS
  layout well and is fast enough when the browser is reused across a job. WeasyPrint
  produced correct shaping but was not installable on this host (missing Pango/Weasy
  system stack), and CSS support is narrower. This host has no Chromium binary, so the
  automated spike test exercises the ReportLab fallback (embedded Noto Sans Ethiopic,
  verified with pypdf) and the Playwright path is code-complete and covered by a
  conditional test. Installing Chromium (`pnpm exec playwright install chromium`)
  enables it without code changes.
- **Consequence:** Document Studio (Phase 5) uses the same renderer interface, so the
  fallback is a safety net, not a second product.

## 2026-11-17 — Local storage driver

- **Decision:** `STORAGE_DRIVER=local` writes to disk in dev; S3/MinIO is wired behind
  the same interface and selected in compose/production.
- **Reason:** No Docker daemon on this host; keeps the upload path testable.

## 2026-11-17 — Module enablement cache

- **Decision:** The enabled/licensed check reads the database per request (indexed
  lookup) rather than caching for a TTL.
- **Reason:** The guide requires toggles to take effect instantly; the query is cheap
  and correctness beats a micro-optimisation. A short cache can be added in Phase 14
  with explicit invalidation.

## 2026-11-17 — Agent orchestration rule (project-wide, until completion)

- **Rule:** If a subagent stops because the model provider's free usage limit is
  reached, and the owner replies **"resume"**, relaunch the same subagent session(s)
  with their previous context and tell them to continue the task they already
  started. If the owner replies **"continue"**, the orchestrator continues the work
  itself instead of relaunching agents.
- **Scope:** Applies to every remaining phase of this project. Agents must still
  follow the build guide task-by-task, run each Verify step, and never weaken tests.
- **Why:** Keeps agent progress recoverable across provider limits without losing
  context or restarting finished work.

## 2026-11-17 — Controller web module list and translations (P0-20)

- **Decision:** `owner/controller-web` keeps its own `LICENSABLE_MODULES` constant
  mirroring `owner/controller-api/controller_api/licenses.py`, and ships a typed
  English message map in `src/i18n.ts`; it renders the shipped `DEFAULT_THEME`
  tokens without calling a theme endpoint.
- **Reason:** The zone boundary forbids importing controller-api source (and it is
  Python), the controller API exposes no translation or theme endpoint yet, and
  P0 only needs the English skeleton plus light/dark switching.
- **Consequence:** When `licenses.py` changes, update `src/lib/types.ts` in the same
  change. Translation/theming can move to API-backed bundles when those endpoints
  exist without touching component code.

## 2026-11-17 — Dev launcher and seed strategy (P0-25)

- **Decision:** `scripts/dev.sh` prefers Docker compose when a daemon is reachable
  and otherwise uses the documented SQLite fallback from the repo root
  (`data/erp_demo.db`, `data/controller.db`). Background PIDs, ports and process
  start times are tracked in `data/dev.pids`; `down` only signals processes whose
  start time and command line still match, walking child processes from those
  tracked roots. Logs live in `data/logs`.
- **Reason:** This build host has no Docker daemon, and the launcher must be safe
  to run twice and must never kill unrelated processes. The SQLite fallback keeps
  `up`/`reset`/`test` usable without containers while compose remains the
  production-shaped path.
- **Consequence:** Alembic revisions are applied only in compose mode; SQLite mode
  lets the app factory create the schema. `reset` deletes only `./data` inside the
  repository (and compose volumes only when this launcher started compose).

## 2026-11-17 — Seed enrollment and license issuance (P0-25)

- **Decision:** The seed writes both databases in-process. It creates the two
  controller users, the `DEMO` school and a canonical enrollment token
  `dev-enroll-DEMO-2026`, then signs a license with the controller's own license
  key and applies it through the normal `apply_license` verification path. It also
  copies the seeded instance public key onto the controller school record.
- **Reason:** Seeding must be deterministic and work without either API running or
  a network round-trip, while leaving the real `POST /controller/v1/enroll` path
  available. The token is created once; repeated seeds reuse it and never create a
  second token. Reused licenses prevent duplicate license rows on repeated seeds.
- **Consequence:** `seed` refuses `APP_ENV=production` before opening either
  database. Manual enrollment can still consume the canonical token later; after
  that the seed reports it as used.

## 2026-11-17 — CI checks and generated-client policy (P0-24)

- **Decision:** CI has separate Python, Node, api-client, i18n and boundary jobs.
  Python is pinned to 3.12 and Node to 22, with uv/pnpm caching. The api-client job
  exports the school OpenAPI document in-process, regenerates the client into a
  temporary file and fails on a diff before running the explicit
  `git diff --exit-code` guard. `--write` is the only mode that updates the
  committed `schema.d.ts`.
- **Reason:** Running the generator without a server keeps the check deterministic
  and catches contract drift in a job that cannot accidentally commit.
- **Consequence:** A backend route/schema change requires
  `./scripts/gen-api.sh --write` in the same change. Controller OpenAPI export is
  optional (`./scripts/gen-api.sh --controller`) and writes under gitignored
  `data/`.

## 2026-11-17 — Mobile app trust, storage and theming (P0-21)

- **Signed directory:** `owner/mobile` verifies the controller's Ed25519-signed
  `GET /controller/v1/directory/resolve` record against an embedded public key,
  pinning `kid` and rejecting altered outer fields, altered JWT payloads, unknown
  keys, expired/future tokens, suspended schools and non-http(s) base URLs. A
  DEV-ONLY keypair is embedded for local demos: the controller must be given the
  matching `DIRECTORY_PRIVATE_KEY` before its first boot (or its key table reset
  once), because auto-generated controller keys will not match. Production builds
  must set `EXPO_PUBLIC_CONTROLLER_DIRECTORY_PUBLIC_KEY` (and
  `EXPO_PUBLIC_CONTROLLER_DIRECTORY_KID`) when the controller uses a real key.
- **Storage:** Profiles, tokens, caches and preferences live in
  `expo-secure-store` under `erp.<instanceId>.*` namespaces; tokens and caches are
  refused unless the stored signed record still verifies. Profile fields are
  rebuilt from the signed payload, so tampered denormalised values cannot change
  the server address or school identity.
- **Crypto pin:** `@noble/ed25519@1.7.3` + `@noble/hashes@1.8.0` are pinned
  because v3 is ESM-only and cannot be `require`d by the Jest environment; v1
  exposes the same real Ed25519 verification synchronously.
- **Native theming:** shadcn-style `oklch()` tokens are converted to sRGB hex or
  `rgba()` before `toReactNativeTheme`, since React Native cannot parse CSS colour
  functions. The conversion is local and applies to both the shipped default theme
  and school themes fetched through the verified base URL.
- **Reason:** Keeps the app offline-capable and content-address-free while making
  every network call derive its origin from a signed controller record.


## 2026-11-17 — P0 walkthrough fixes and the smoke e2e harness

- **`via` is server-derived.** `@erp/api-client` no longer sends a hard-coded
  `X-Client-Via: web` header. It relabelled controller support sessions as web
  traffic in the audit vault (`via=web` while `actor_type=controller`). The
  server already derives `via` from the token; clients that need to identify
  themselves (mobile) pass the new optional `clientVia` option.
- **Translation fetches are bound.** `TranslationLoader` calls
  `globalThis.fetch.bind(globalThis)`; browsers throw "Illegal invocation" when
  `fetch` is invoked through an object property, which blanked the school UI to
  raw i18n keys. `loadMany` now tolerates a failing namespace (a disabled module
  returns 403 for its own bundle) instead of discarding every bundle.
- **Zone boundaries are proven by fixtures.** `tests/test_zone_boundaries.py`
  runs the real `.importlinter` against a temporary copy of the packages and the
  real `eslint.config.mjs` against fixture text, so a deliberately violating
  Python/TypeScript file must fail the check. This is P0-01b's Verify step and
  runs in the normal pytest suite.
- **Smoke e2e is a standalone stack.** `./e2e/run.sh` seeds disposable SQLite
  databases, starts both APIs and both web apps on the standard dev ports, runs
  the Playwright spec, and tears everything down. The spec stands in for Celery
  beat via `e2e/sync.sh` (heartbeat + audit shipping) because the e2e stack has
  no Redis. `E2E_EXTERNAL=1` targets an existing `./scripts/dev.sh up` stack.
  CI runs the same script in the `e2e` job.
- **Dev directory key.** `dev.sh`/`dev.ps1` now export the DEV-ONLY
  `DIRECTORY_PRIVATE_KEY`/`DIRECTORY_KID` whose public half is embedded in the
  mobile app, so the P0-21 manual Expo Go flow works on a clean clone. A database
  seeded before this change keeps its generated key; `reset` once to adopt it.

## 2026-11-17 — P1-01 API conventions

- **Pagination is keyset.** The shared envelope is `{items, next_cursor, total?}`
  with `limit` (1–200, default 25), `cursor`, `sort` and `order`. Cursors are
  base64url JSON containing the last row's sort value and primary key, so pages
  stay stable when rows are inserted. A cursor reused with a different sort is
  rejected with `INVALID_CURSOR`.
- **Filters are explicit.** Each router declares the allowed filters with a
  `FilterSpec`; unknown names are `INVALID_FILTER`. `contains` escapes `%` and
  `_`, so a search for `100%` matches the literal text.
- **Idempotency lives in the school database.** `Idempotency-Key` is optional;
  when present, the first completed JSON response is stored for 24 hours under
  `sha256(key)` scoped to `METHOD path`. The fingerprint covers the body,
  query string and `Authorization` header, so the same key with a different
  payload returns `409 IDEMPOTENCY_KEY_REUSED`, and a concurrent replay returns
  `409 IDEMPOTENCY_IN_PROGRESS`. Non-JSON and 5xx responses are not stored.
  Payment webhook keys must still be verified (signature/amount) before they
  reach a handler; idempotency only prevents duplicate side effects.
- **Optimistic concurrency is opt-in per update.** `apply_row_version` checks the
  client's `row_version` (body field or `If-Match`), applies the allowed fields
  and increments only when something changed. A mismatch is `409 CONFLICT` with
  `details = {expected, current, state}` instead of a silent overwrite.
- The sample note `PATCH` reuses `sample.notes.create` as its permission until
  P1-05 introduces the full permission matrix; its purpose is to prove the
  convention end to end.

## 2026-11-17 — P1-02 soft delete

- **Filtering is automatic.** Importing `core.db` registers a `do_orm_execute`
  listener that applies `with_loader_criteria(SoftDeleteMixin, ...)` to every
  ORM select unless the statement opts out with
  `execution_options(include_deleted=True)`. Explicit `.where(deleted_at is
  None)` clauses remain harmless and keep count/subquery queries correct.
- **Restore is a separate audited action.** `soft_delete` stamps
  `deleted_at`/`deleted_by`, bumps `row_version` and writes a `*.delete` entry;
  `restore` clears the stamps, bumps the version and writes a new `*.restore`
  entry. The original delete entry is never edited, so the hash chain stays
  valid.
- **Partial indexes exclude dead rows.** Business tables that list live rows add
  a dialect-aware partial index (`WHERE deleted_at IS NULL`); the sample note
  index is `ix_sample_notes_live`. PostgreSQL and SQLite both support this.
- The sample note delete/restore endpoints keep using `sample.notes.create` as
  their permission until P1-05.

## 2026-11-17 — P1-03 typed layered settings

- **Three layers, one table.** Values resolve `code` (Pydantic defaults) <
  `central` (controller policy) < `instance` (the school). `settings` stores one
  row per `(layer, module, key)`; clearing an instance value soft-deletes the
  row so the effective value falls back to central or code. There is still one
  physical database locally; the `central` layer is written through the service
  only (the controller sync will call it in a later phase), while the HTTP API
  writes `instance`.
- **Modules own their schema.** `ModuleManifest.settings_schema` points at a
  Pydantic model; `field_specs` flattens it to dotted keys and derives the form
  metadata (`type`, `enum`, `minimum`, `maximum`, `max_length`, `secret`,
  `label_key`, `default`). The web Settings page is rendered entirely from that
  metadata, so a new module setting needs no bespoke React page.
- **Validation is whole-model.** A single PUT validates the candidate against
  the complete model (not just the one field), so cross-field/default
  constraints hold; failures return `422 VALIDATION_ERROR` with
  `message_key=error.invalid_setting` and the pydantic locations.
- **Every change is audited.** `PUT /settings/{module}/{key}` writes
  `settings.update` and `DELETE` writes `settings.clear`, both with
  `before/after = {value, source}`. The audit entry uses the module/key as the
  entity id (`core.school_profile.name`).
- Settings labels live under `settings.<module>.<key>` in the owning module's
  i18n bundle; the `core` bundle also carries the page chrome and enum labels.
- `settings.view` gates the page/navigation, `settings.manage` gates writes; the
  seeded director gets both, the `limited` test role gets neither.

## 2026-11-17 — P1-04 auth hardening

- **Account lockout is per user, not per IP.** Five failed passwords or TOTP /
  recovery codes within a session lock the account for 15 minutes
  (`423 ACCOUNT_LOCKED` with `locked_until`). A successful login clears the
  counter, and an expired lock clears itself on the next attempt.
- **Online guessing limits are per IP and in-process.** `SlidingWindowLimiter`
  guards login (20/min) and password-reset requests/attempts; the interface is
  tiny so moving to Redis when the shared cache lands is a one-file change.
  Tests reset the global limiters between apps to keep cases isolated.
- **TOTP is implemented in-repo** (RFC 6238, SHA-1, 6 digits, 30-second period,
  ±1 window) instead of adding a dependency. Secrets are encrypted at rest with
  Fernet derived from `SECRET_KEY`; recovery codes are stored as SHA-256 hashes
  and consumed one at a time.
- **2FA can be forced by role.** `roles.require_totp` makes `require()` reject
  every endpoint except `/api/v1/auth/2fa/*` with `403 TOTP_ENROLLMENT_REQUIRED`
  until the user confirms enrollment. Login still succeeds so the app can show
  the enrollment screen; `/me` reports `must_enroll_2fa`.
- **Password policy:** at least 12 characters with a letter and a digit,
  reported as `422 WEAK_PASSWORD` with the unmet rules. Reset tokens are stored
  hashed, expire in 30 minutes, are single use, and invalidate all other
  outstanding email/SMS tokens plus every refresh session for that user.
  Email carries a long link token; SMS carries a 6-digit code through the
  logging adapter until a provider is chosen (SMS is a stub, not a blocker).
- **Web sessions use a path-scoped HttpOnly refresh cookie plus a readable CSRF
  cookie** (`erp_refresh`, `erp_csrf`, path `/api/v1/auth/web`). Every refresh
  must echo the CSRF value in `X-CSRF-Token`; cookies are `Secure` in production.
  The access token stays short-lived and is returned in JSON. The school web app
  still uses the JSON token flow until the roles/users UI task (P1-07) switches
  it to the cookie flow.
- **Logout revokes every refresh family for the user.** Per-device logout and
  revocation is available through `GET/DELETE /auth/sessions`; the session list
  groups rotations by family and marks the current one.

## 2026-11-17 — P1-05 full RBAC

- **Scopes are a containment rule, not a hierarchy of magic strings.**
  `core/rbac/scopes.py` defines the vocabulary (`all`, `department`,
  `assigned_subjects`, `own_class`, `own_children`, `self`); `all` covers any
  requested scope, otherwise the scope must match exactly. Modules declare which
  scopes their permissions accept, and `require(permission, scope=...)` uses the
  same check as the menu and AI tool filters. Data resolvers (a teacher's
  sections, a parent's children) land with the domain modules.
- **Denies always win and are per permission.** Active `deny` overrides remove
  the permission regardless of role grants or insertion order; expired rows are
  ignored. Deny rows are stored with scope `all` so the outcome is unambiguous.
  Grants with an expiry are the delegation mechanism.
- **A caller can only grant or deny what they hold.** Role permission additions,
  role assignment (all permissions of the role) and every override are checked
  against the caller's own effective permissions and scopes; a wildcard caller
  (`*`) is the documented exception. This prevents a `roles.manage` holder from
  minting `users.manage`.
- **Roles are deactivated, never hard-deleted.** `DELETE /rbac/roles/{id}` sets
  `is_active=false`; inactive roles contribute no permissions and disappear from
  `/me`. Join rows are the only rows replaced/removed when a role's permission
  set or a user's assignment changes.
- **All RBAC mutations are audited** (`rbac.role.create|update|deactivate|
  permissions`, `rbac.user.role_assigned|role_removed|override_set|
  override_cleared`) with before/after and, for overrides, the caller's reason.
- **The permission matrix test is executable.** It walks every mounted API route,
  collects the real `require()` guards, and evaluates each guard for every seeded
  role through the same dependency code the request would use. It also fails if a
  route declares a permission that no manifest defines.

## 2026-11-17 — P1-06 shipped default roles

- **Twelve roles are shipped as ordinary editable roles.** Bootstrap creates
  Super Admin, Director, Academic Head, Department Head, Registrar, Teacher,
  Homeroom Teacher, Accountant, HR Officer, Librarian, Parent and Student when
  they are missing. They are marked `is_system` for display, but the RBAC API
  can rename, re-permission, deactivate or reactivate any of them: “default”
  means a starting point, not a protected definition.
- **Bootstrap never overwrites local edits.** `ensure_default_roles()` only adds
  missing roles and their permissions. An existing role keeps its name,
  description, active flag, 2FA flag and permission set across restarts.
  Unknown permission codes are intersected with the manifests currently
  installed; the wildcard `*` is kept as-is. Later module installs therefore do
  not silently widen an existing role — a school reviews and adds those
  permissions explicitly, so an upgrade cannot expand access behind its back.
- **The demo seed is the explicit reset path.** `scripts/seed.py` calls the
  same helper with `reset_permissions=True`, which restores names and the
  documented permission matrix. `limited` remains a demo-only custom role.
- **Seeded roles do not force 2FA.** A fresh instance has no TOTP secret yet, so
  forcing it would lock the only owner out. The Super Admin enables
  `require_totp` per role after the first login.
- **Replacing a role's permissions is atomic and uniqueness-safe.** The API
  bulk-deletes the old pairs before inserting the new set, so unchanged pairs
  cannot collide with `uq_role_perm_scope`.

## 2026-11-17 — P1-07 roles and users UI

- **Inviting a user creates the account and emails a single-use password
  link.** The account starts with `must_change_password=true` and a random
  password that is never revealed; the link uses the same hashed
  `PasswordResetToken` flow as forgot-password. In development the response also
  returns the link so the log-only mail adapter does not block testing. The
  invitation is audited as `auth.user.invited`. Reset and invitation links point
  at the new `web_base_url` (the SPA `/reset-password` screen), not the API
  origin; the same screen serves forgot-password.
- **Inviting with roles needs `roles.manage` and remains bounded by delegation.**
  A `users.manage` holder can invite a person without roles, but assigning
  starting roles requires `roles.manage` and every role permission must satisfy
  “cannot grant what you do not hold”.
- **Deactivation is a soft flag and revokes every session.** `is_active=false`
  immediately rejects existing access tokens and future logins; refresh families
  are revoked. Users cannot deactivate their own account. Reactivation does not
  restore old sessions.
- **The permission matrix is the role editor.** It groups permissions by module,
  renders each scope the manifest accepts, and preserves the `*` wildcard as an
  explicit “full access” switch. Only a wildcard holder can add `*`; preserving
  an existing wildcard grant does not require one.
- **Menus are derived from the same permission set and refreshed after edits.**
  Navigation adds Users for `users.view|users.manage`, Roles for
  `roles.view|roles.manage`, and Settings for `settings.view`. Role, assignment
  and deactivation mutations invalidate the navigation query and re-read `/me`,
  so the current session’s menu changes without a reload.

## 2026-11-17 — P1-08 module management UI

- **The module state API is permissioned.** `GET /system/modules` now needs
  `modules.view`; `PUT /system/modules/{key}` keeps `modules.manage`. The API
  returns the three gates (`licensed`, `enabled`, `permitted`) plus `available`,
  the module's resolved dependencies and dependants, and `blocked_by` keys so
  the UI can explain a disabled toggle without guessing.
- **Dependency rules stay server-side and are mirrored in the UI.** Enabling a
  module with an unavailable dependency returns `409 CONFLICT` with
  `modules.dependency_disabled`; disabling one with enabled dependants returns
  `modules.dependants_enabled`. The page disables those toggles and shows the
  names involved, but still renders any server conflict (for example a stale
  list or a race) as an alert.
- **Core modules cannot be toggled and unlicensed modules cannot be enabled.**
  An already-enabled module that lost its licence can still be disabled, so an
  administrator is never trapped by an expired licence. `permitted` is shown as
  information about the current user and does not change the school-wide toggle.
- **Settings → Modules is reachable from both the sidebar and Settings.**
  Navigation adds Modules for `modules.view|modules.manage` at
  `/settings/modules`; the Settings page also links there for holders of either
  permission. Read-only viewers see the full state but no enabled switches.
- **Toggles are audited with the full gate snapshot.** `modules.toggle` records
  `licensed`, `enabled` and `available` before and after, so a later investigation
  can distinguish a licence change from an administrator's action.
- **Wildcard holders count as settings managers.** The Settings page now treats
  `*` like `settings.manage` (and like the module permissions), matching the
  backend's wildcard semantics.

## 2026-11-17 — P1-09 audit completion

- **Actor and channel vocabularies are enforced at write time.**
  `actor_type ∈ {user, ai, controller, automation, system}` and
  `via ∈ {web, mobile, api, ai, controller, automation}`. `record()` rejects
  anything else, and `Principal.on_behalf_of`/an explicit `on_behalf_of`
  argument fills the delegated-actor field. `reason` falls back to the
  principal's controller-session reason.
- **Clients may only claim client channels.** `X-Client-Via` is honoured for
  `web`, `mobile` and `api`; `ai`, `controller` and `automation` stay
  server-derived. Controller principals ignore the header entirely, so a
  support session can never be relabelled as ordinary web traffic.
- **Reads of sensitive records are audited.** `GET /audit/activity/{seq}`
  records `audit.activity.read` and `GET /rbac/users/{id}/permissions` records
  `rbac.permissions.read`, with actor, `via`, IP and user agent. These routes
  commit the read entry themselves because a GET has no later mutation to commit.
  Ordinary list endpoints remain unaudited to avoid log floods; P1-10 owns the
  activity-history visibility rules.
- **Sequence allocation takes a PostgreSQL advisory lock.**
  `pg_advisory_xact_lock` serialises `max(seq) + 1` until commit; SQLite keeps
  its existing single-writer behaviour. The lock key is a fixed constant so all
  app processes agree on it.
- **Audit shipping retries with exponential backoff.** Outbox rows carry
  `available_at`, `last_attempt_at` and `last_error`. A failed ship increments
  `attempts`, stores the (bounded) error and delays the next attempt by
  `base × 2^(attempts-1)`, capped by `AUDIT_RETRY_MAX_SECONDS`. The failure is
  committed before the exception leaves the service, so an offline controller
  does not spin every beat tick. Successful shipping clears the error.
- **Celery beat ships every 30 s and verifies nightly.** `erp.ship_audit` and
  `erp.verify_audit_chain` are scheduled from settings
  (`AUDIT_SHIP_INTERVAL_SECONDS`, `AUDIT_VERIFY_INTERVAL_SECONDS`). The verify
  task logs an error when the chain is broken instead of silently returning.
- **Heartbeats report the real chain head.** `audit_chain_head`/`audit_seq` come
  from the latest local entry, letting the controller detect gaps between what
  was ingested and what the instance holds.

## 2026-11-17 — P1-10 activity history visibility

- **Activity is a business view of the audit chain, not a raw log dump.** Tier A
  entries only are exposed: controller-session plumbing, password reset/session/
  TOTP actions and `jobs.`, `system.`, `worker.` and `infra.` actions stay out.
  `auth.user.invited` and `auth.user.updated` remain visible because they are
  real user-management events. Entries are serialised with business fields only
  (`actor_name`, `on_behalf_of_name`, `before`, `after`, `reason`, …); IP
  addresses, user agents, hashes and request identifiers are never returned.
- **Scope comes from the permission, not a second request parameter.**
  `audit.activity.view` is granted with a module scope; `all` or `*` sees every
  module. A request may narrow to a module inside that scope. Asking for a module
  outside the scope returns `403 PERMISSION_DENIED`, and an entry outside the
  scope behaves as absent (`404` on detail) so existence is not leaked.
- **Super Admin actions need a second permission.**
  `audit.activity.view_admin_actions` unmasks entries whose actor currently
  holds the active `super_admin` role. Controller actions stay visible and are
  labelled as controller activity because they are accountability events in
  their own right, not ordinary admin noise.
- **Filters and option lists are server-driven.** The list accepts actor,
  module, entity type/id, action and inclusive date boundaries with cursor
  pagination. `GET /audit/activity/options` returns only the modules, actions and
  actors the caller may see, so the UI never offers a filter that would return
  an empty or forbidden result.
- **The UI lives at `/activity` and is permission-gated.** Navigation adds an
  Activity item for `audit.activity.view`. The page shows human labels for
  modules and actors, renders a before/after diff per entry, treats `*` as a
  wildcard permission, and explains a permission denial inline instead of
  rendering an empty history.

## 2026-11-17 — P1-15 Ethiopian calendar vectors

- **The arithmetic follows the standard JDN formula** `1723856 + 365*year +
  floor(year/4) + 30*month + day - 31` with `year % 4 == 3` as the leap rule
  (Pagume has six days). Both the TypeScript and Python packages implement it
  directly and are cross-checked by round-trip tests over 100+ years.
- **Published dates are used as vectors:** 1 Meskerem 2016 = 12 Sep 2023 and
  1 Meskerem 2017 = 11 Sep 2024 (Ethiopian New Year announcements), Pagume 6
  2015 = 11 Sep 2023, and Genna/Timkat 2017 = 7/19 Jan 2025. Genna falls on
  7 **or** 8 January depending on whether the preceding Ethiopian year was a
  leap year, so tests use the year where the published date is unambiguous.
- **Storage stays Gregorian ISO.** The picker converts only for display and
  always emits `YYYY-MM-DD`; no Ethiopian date is ever persisted.

## 2026-11-17 — P1-16 money semantics

- **No floats cross a boundary.** Strings, `Decimal` (Python) and the decimal
  text of JS numbers are parsed digit-by-digit and rounded half-up on the third
  decimal, so `1.005` is 101 santim and never 100. Values above the signed
  64-bit BIGINT range (Python) or `Number.MAX_SAFE_INTEGER` (TypeScript) are
  rejected rather than silently truncated.
- **Integer inputs mean different things by language, deliberately.** In
  TypeScript a `number` argument is birr (`parseMoney(1250) === 125000`); in
  Python an `int` is already the storage unit (`parse(1250) == 1250`) while
  strings and `Decimal` are birr. API payloads always carry money as strings,
  so this only affects in-process helpers.
- **Allocation sends leftover santim to the largest weights first** (ties by
  input order), which is stable and auditable. Negative amounts allocate the
  absolute value and reapply the sign, so shares always sum exactly to the
  input.

## 2026-11-17 — P1-17 custom fields engine

- **Definitions are data, values stay in the entity's `custom` JSON column.**
  `custom_field_defs` holds the key, i18n label/help keys, type, bounds,
  options, order and role visibility; no per-field ALTER TABLE is ever needed.
  Supported entity types are a registry (`person`, `student`, `staff`,
  `guardian`, `admission_application`) so a typo cannot create a silently
  orphaned definition.
- **Validation is server-side and typed.** Text, long text, integer, decimal
  number, boolean, ISO date, single select and multiselect all validate with
  i18n error keys and per-field details (`field`, `code`, `message_key`,
  `params`). Floats are rejected for numeric fields, and decimals are stored as
  canonical strings, keeping the no-float rule for marks and money. Unknown
  keys are rejected so typos are not hidden inside JSON.
- **Partial updates merge.** Person updates validate supplied keys only, clear
  a key when the value is emptied, and leave untouched keys alone. Required
  fields are enforced on create, not on every partial edit.
- **Visibility is role-scoped and not query-overridable.** A definition with no
  `visible_roles` is public to everyone holding `custom_fields.view`; otherwise
  only members of those roles (or a wildcard Super Admin) see it. There is no
  `include_hidden` request flag, so hidden definitions cannot be enumerated.
- **Labels are translation keys, never stored strings.** Field labels and help
  text must match `a.b` style keys, so the Translation Editor can translate
  them like any other UI text and both scripts stay in sync.
- **Definitions are audited and soft-deleted** (`custom_fields.create/update/
  delete`, entity type `custom_field_def`). A deleted definition is hidden from
  forms immediately; existing entity JSON keeps its historical values.

## 2026-11-17 — P1-18 translation editor

- **English is the source column; the target is the effective target row.**
  Each editor row is one `(namespace, key)` pair. `source` always comes from
  the effective English row and `value` from the most specific target layer
  (`default < central < school`). A key with no target-locale row is reported
  as `missing` even though the runtime still falls back to English, so the
  editor never hides untranslated text behind the fallback.
- **The school app only writes the `school` layer.** Creating or editing a
  translation never mutates a bundled default or a central entry. Reset
  soft-deletes the school override and restores the underlying default or
  central value, so the original rows remain auditable and a later edit
  restores the same override row instead of creating a duplicate.
- **Imports are all-or-nothing.** The whole file is parsed, every key must
  already exist in the module (typos cannot create orphan translations), and
  every value is validated before the first write. `dry_run` reports what
  would change without writing. Imports record one `i18n.import` audit entry
  with the namespace, locale, format and changed keys; this action is not
  revertible as a single batch.
- **`needs_review` is a real status, not a label.** Import can insert drafts
  as `needs_review` (the future "Suggest with AI" flow uses the same status),
  and the editor can promote them to `approved`. Status filters query the
  effective target row.
- **Editor routes live under `/api/v1/i18n/editor`** and are registered before
  the public `/{locale}/{namespace}` bundle route. Otherwise `editor` would be
  parsed as a locale. Bundle responses keep their ETag and are re-fetched by
  the web and mobile loaders on the next load, so an edit appears without a
  redeploy.
- **`translation_entries` now carries `row_version`** (in addition to
  `deleted_at`/`deleted_by` from migration `0011_i18n_soft_delete`) because
  every business table follows the shared soft-delete/row-version rules and
  reset is a soft delete.

## 2026-11-17 — P1-19 "Suggest with AI" hook

- **The editor invokes the action registry, never a model directly.** The
  endpoint `POST /api/v1/i18n/editor/suggest` looks up
  `i18n.suggest_translation` (permission `i18n.manage`, risk `write`) and calls
  its registered handler, so the AI tool list, permissions and previews cannot
  drift from the editor button.
- **No provider means a clear state, not a fake translation.** The endpoint
  returns HTTP 200 with `configured: false`, `status: "not_configured"` and
  `message_key: "ai.not_configured"` when there is no API key, the provider is
  the `fake` echo, or no suggester has been registered. Phase 9 registers the
  real suggester through `register_translation_suggester`.
- **Suggestions are drafts and never overwrite human work.** A generated value
  is stored on the `school` layer with `source="ai"` and
  `status="needs_review"`. If a live school override already exists, it is left
  untouched and the response returns `written: false` plus the draft so the
  editor can compare them. Every written draft is audited as `i18n.suggest`.
- **English is not a target.** Suggestions are rejected for `locale=en` because
  English is the source column; the editor only offers the button on target
  locales.

## 2026-11-17 — P1-20 i18n tooling and Ethiopic font

- **A local ESLint rule bans hard-coded UI text.** `i18n/no-literal-ui-text`
  reports non-empty JSX text and literal values for `title`, `placeholder`,
  `aria-label`, `alt` and `label` in the web, controller-web and mobile apps
  (test files are excluded). Elements marked `aria-hidden="true"` are treated
  as decorative. The rule intentionally does not guess at runtime-built
  strings; those still need review.
- **Missing English keys fail CI; missing Amharic keys are a report.**
  `scripts/check-i18n.py` fails when source code references a key that is not
  in the English bundle, when an Amharic bundle contains a key English does
  not, or when strict mode (`--strict-am`) is requested. Plain missing Amharic
  keys print a backlog summary and exit 0 so translation work does not block
  code delivery; the Translation Editor's `missing` filter is the source of
  the list. `ERP_I18N_ROOT` lets the checker run against a fixture tree.
- **Noto Sans Ethiopic ships with both clients.** The same OFL-licensed TTF
  (and its `OFL.txt`) is copied into `school-erp/web/public/fonts` and
  `owner/mobile/assets/fonts`. Web declares it with `@font-face` +
  `font-display: swap`; mobile loads it with `expo-font`'s `useFonts` and uses
  it in the shared text primitives, so Ge'ez glyphs do not depend on the
  device's installed fonts.

## 2026-11-17 — P1-21 Theme Manager

- **The stored token map is the single source of truth.** `themes.tokens`
  holds `{light, dark}` exactly as the author wrote it. Web CSS variables and
  the mobile React Native object are both generated from that map
  (`core/themes/tokens.py`), so a theme cannot drift between platforms. The
  builtin default is a real row (`key=default`) and also a hard-coded fallback
  for the case where the database is empty or the row is corrupt.
- **Import accepts the shapes schools already have.** CSS paste reads
  `:root`/`html`/`body` as light and `.dark` as dark, plus `@theme` shared
  values; JSON accepts a flat `{light, dark}`, `{tokens: {light, dark}}`,
  shadcn/tweakcn `{cssVars: {theme, light, dark}}`, a registry item, or a
  registry index whose first theme item is used. Flat single-mode JSON is
  rejected rather than guessed. Colour names are normalised (`--color-*` and
  `--*` are the same token).
- **Validation is strict and explains itself.** Both modes, every colour,
  chart and sidebar token, a CSS length for `radius`, resolvable colours (no
  dangling `var()`) and eleven WCAG 2.2 AA text/background pairs at 4.5:1 are
  required. Failures return `422` with `message_key: error.theme.invalid` and
  a list of complete-sentence issues (mode, tokens and measured ratio included)
  so the UI does not need to translate backend internals. Unreadable pairs are
  rejected by the shipped defaults themselves: light `muted-foreground` is
  `oklch(0.53 0 0)` and dark `destructive` is `oklch(0.577 0.245 27.325)`.
- **Preview never writes.** `POST /themes/preview` parses and validates in
  memory, returns the tokens, CSS, mobile objects, the full contrast report and
  the builtin fallback when invalid. `POST /themes/import` repeats validation
  before the first write, so a client that skips preview still cannot store an
  unusable theme.
- **A broken stored theme is never served.** Reading the active theme validates
  the stored tokens; if they fail, the response is the builtin default with
  `fallback: true` and the issues in `reason`. The same applies to a user's
  chosen theme. This is the "broken theme falls back to default" contract.
- **School availability and the school default are separate flags.**
  `is_active` means "users at this school may choose it"; `is_default` is the
  school-wide fallback. Hiding a theme keeps it installed. The current default
  cannot be hidden and the builtin default cannot be hidden or deleted; delete
  is a soft delete. The first default is created by bootstrap.
- **Per-user choice is authenticated but not privileged.** Every signed-in
  user may set `theme_key`/`theme_mode` through `PUT /themes/preference`; the
  choice is validated against the school's available themes and audited as
  `user.theme_preference`. `GET /themes/available` requires only a session.
  Managing themes requires `themes.view`/`themes.manage`.
- **Clients resolve the theme on every load.** Web applies generated CSS custom
  properties and re-applies the shipped defaults first so removed tokens cannot
  linger; mobile sends its session token (when present) so the backend returns
  the user's own theme, caches the validated definition per school, and falls
  back to `DEFAULT_THEME` when the stored theme is broken.
- **The committed OpenAPI client was regenerated.** `shared/ts/api-client/src/schema.d.ts`
  now includes the P1-18 editor routes (previously missed) and the P1-21 theme
  routes. The change is additive within `/api/v1`.

## 2026-11-17 — P1-22 Files service

- **Storage is an interface with two drivers.** `STORAGE_DRIVER=local` writes
  under `STORAGE_DIR` and is the default for development and this host, which
  has no Docker or MinIO. `STORAGE_DRIVER=s3` talks to any S3-compatible
  endpoint using a dependency-free SigV4 query presigner (`core/files/s3.py`);
  both path-style and virtual-host-style buckets are supported. Adding boto3
  would have pulled a large SDK in just to sign URLs, so signatures are built
  from the standard library and requests use httpx.
- **Signed URLs are absolute and short-lived.** Local links are HMAC-SHA256
  over `GET`, the object key and the expiry, served by
  `/api/v1/files/content/{key}`. S3 links go straight to the bucket. The
  default TTL is `STORAGE_SIGNED_URL_SECONDS` (600) and callers may request up
  to 24 hours. Local URLs use `PUBLIC_BASE_URL`, so a web page can put the URL
  in an `img`/`a` tag without knowing the API host.
- **Uploads are inspected, not trusted.** The extension must be in the
  allowlist, the browser-declared MIME must match (octet-stream is tolerated
  for clients that cannot know), and the body must agree: Pillow decodes
  images and checks the detected format, PDFs must start with `%PDF-`, Office
  files must be ZIPs containing their main part, and CSV/text must be UTF-8
  without NUL bytes. SVG is intentionally excluded because it can carry
  script. Empty files and files over `STORAGE_MAX_UPLOAD_BYTES` (25 MB) are
  rejected before anything is written.
- **Files are private by default.** A private file is visible to its uploader
  and to holders of `files.view`; other signed-in users receive 403. Public
  files are visible to any session, but they still require a signed URL for the
  bytes. `files.manage` holders and the uploader may soft-delete. Delete stamps
  the row and the content route stops serving it immediately; the object stays
  in storage so the audit trail and recovery remain possible.
- **Object keys are generated, never user-supplied.** Keys look like
  `yyyy/mm/<uuid><ext>`; the local driver additionally rejects absolute paths
  and `..` segments and resolves symlinks before reading or writing.
- **Thumbnails are a background job.** Image uploads enqueue
  `files.thumbnail` with the file id. The worker creates a max-320 px JPEG at
  `thumbnails/<key>.jpg` and stores its key on the row. Test runs do not call
  the broker: the service function is exercised directly, avoiding both a Redis
  dependency and accidental writes to the production database.
- **The upload component posts multipart through the shared client.**
  `createApiClient` gained `postForm`, which deliberately omits
  `Content-Type` so the browser adds the boundary. `FileUpload` enforces the
  size limit client-side and maps 413/415 failures to translated messages; it
  is reusable by the setup wizard (P1-24) and student documents.
- **`files.*` is declared but not added to the shipped role matrix.** The
  P1-06 default roles are asserted exactly by tests and the documented matrix
  did not include file permissions. Schools (and the P1-SEED limited role) can
  grant `files.view`, `files.upload` and `files.manage`; the Super Admin holds
  them through `*`.

## 2026-11-18 — P1-23 Notification service

- **One `notifications` row per recipient.** A template is shared, but the
  in-app centre is personal: each row stores the rendered title/body, the
  template key, the variables and the chosen channels. The message is rendered
  in the recipient's locale when it is sent, so switching language later does
  not rewrite history (and an Amharic notification stays Amharic).
- **Templates hold translation keys, never literal text.** `title_key` and
  `body_key` point into a namespace (default `core`); variables use
  `{{name}}` placeholders. This keeps the i18n rule intact: an edited Amharic
  label changes future notifications without a redeploy. The API rejects
  literal strings that do not look like keys. Three templates ship from
  bootstrap (`account.welcome`, `academics.results_published`,
  `finance.invoice_overdue`); system templates can be edited but not deleted,
  and all templates are soft-deleted.
- **In-app is immediate; external channels are queued.** Creating a
  notification writes an in-app row (status `sent`) plus one `delivery_logs`
  row per channel. Email, SMS, push and Telegram start `queued` and a
  `notifications.delivery` job delivers them; missing email/phone marks that
  channel `skipped` with a reason instead of failing the whole message. Test
  runs call `deliver_notification` directly so no broker or Mailpit is needed.
- **Push is a minimal logging stub until P11-12.** `app.state.push` implements
  the same interface the signed controller relay will use. It records only the
  title, the deep link and the notification id; body text, marks, names and
  amounts never enter a push payload. `build_push_adapter` is the single switch
  point for the real relay.
- **Delivery logs keep the address, the API masks it.** Operators need the
  real email/phone/device id to diagnose failures; the delivery-log endpoint
  returns `f***@domain` and `***1234`. Attempt counts and the last error are
  visible, which is what the jobs UI needs for retry.
- **Sending and reading are audited; message bodies are not.** `notification.send`
  records the template, recipient id and channels only, and marking read /
  read-all records a count. The audit chain therefore never becomes a copy of
  private message content.
- **`notifications.*` is declared but not granted by default.** As with
  `files.*`, the P1-06 matrix is asserted exactly and unchanged. Every signed-in
  user can read and mark their own inbox (session-scoped, IDOR-safe: another
  user's id returns 404); template and delivery management requires
  `notifications.view`/`notifications.manage`.
- **The notification centre is web-only for now.** Mobile notification UI is
  part of the Phase 12 mobile parity sweep; the API and rendered rows are
  already platform-neutral.

## 2026-11-18 — P1-24 Instance setup wizard

- **"Set up" is derived, not stored.** An instance still needs setup exactly
  while it has zero users. There is no `setup_complete` flag or table to drift
  out of sync, and a soft-deleted or deactivated user cannot reopen the window
  because the check counts every account. The public `POST /api/v1/setup`
  re-checks at the top of its transaction and returns `409 SETUP_COMPLETE`
  afterwards.
- **The whole wizard is one transaction.** The first admin, role assignment,
  settings overrides, theme default and logo metadata commit together. File
  upload and `set_default_theme` gained a `commit=False` mode so the setup
  service can validate everything first and roll back as a unit. On PostgreSQL
  a transaction-scoped advisory lock serialises two simultaneous setup calls;
  SQLite serialises writers at commit and the wizard only submits once.
- **The logo arrives as a base64 data URL.** The files upload route requires
  `files.upload`, and nobody is signed in yet, so the wizard sends the image
  inline. It is decoded through the same `validate_upload` path (extension,
  MIME and magic-byte sniffing, 25 MB limit, no SVG) and stored as a **public**
  file owned by `school/profile`. Logos do not get thumbnails.
- **Profile and logo live in settings.** `school_profile.logo_file_id` was
  added to the typed core settings model, so the existing layered-settings
  machinery, validation and form metadata apply. The status endpoint resolves
  a fresh signed URL from that id; it never returns a raw storage key.
- **Theme selection updates both sources.** `branding.theme` records the
  school's choice for the settings UI, and the chosen theme becomes
  `Theme.is_default` because `active_theme` resolves the school default from
  the themes table, not from settings.
- **Setup returns a real session.** The first Super Admin chooses their own
  password (the shared policy applies; no forced change) and the API issues the
  normal access/refresh pair. The web wizard adopts that session and lands on
  the dashboard instead of asking for a second sign-in.
- **The sign-in screen redirects when setup is pending.** It makes one
  best-effort public status call; if the backend is unreachable the form still
  renders, and if setup is complete the call is cached for a minute. Direct
  visits to `/setup` show a "already complete" card with a sign-in link.
- **Setup is audited as a single instance event.** `setup.complete` records the
  applied profile, logo id, theme and admin id; `auth.user.created` records the
  admin, and the reused theme/file services add their own `theme.default` and
  `file.upload` entries. No password or logo bytes enter the audit chain.


## 2026-11-18 — P1-25 Jobs UI

- **The API never returns `Job.error`.** Workers store the raw exception for
  operators, but SQL, file paths or provider responses must not reach a user.
  The list view exposes only `error_key`, one of a small set of translated
  messages chosen by job kind, and an unknown kind falls back to a generic
  failure message. Tests assert the raw text is absent from the response body.
- **Retry is a separate permission.** `jobs.view` shows the queue (director
  and academic head already held it); the new `jobs.manage` gates
  `POST /jobs/{id}/retry`. As with `files.*`, `jobs.manage` is declared but not
  added to the shipped default-role matrix, so schools can grant it without
  changing the documented defaults; the Super Admin holds it through `*`.
- **Retry resets the row and audits it.** Only `failed` jobs are accepted
  (`409 JOB_NOT_FAILED`); unsupported kinds (`422`) and missing payload ids
  (`422`) are refused before any mutation. A retry clears progress, error,
  result and timestamps, records `job.retry` with the before/after views, and
  re-enqueues through the same Celery task. Queueing is skipped under
  `app_env=test` so no test run touches Redis.
- **Notification retries requeue failed channels first.** `deliver_notification`
  only processes `queued` delivery logs, so the retry path moves that
  notification's `failed` logs back to `queued` and clears their error while
  keeping `attempts` as history. `skipped` logs are deliberately untouched:
  they were skipped for a reason (no phone number, no adapter) and would only
  be skipped again.
- **The page polls only while work is active.** `GET /jobs` supports `status`,
  `kind`, `limit` and `offset`; an unknown status returns `INVALID_FILTER` with
  the allowed list. The web page refetches every five seconds only when a
  visible row is `queued` or `running`, so a quiet page makes no requests.
- **Retry history is preserved.** The audit chain keeps every failed attempt;
  the single mutable row is restored to `queued`, matching the platform rule
  that jobs are operational state rather than an append-only record.

## 2026-11-18 — P1-26 API compatibility guard

- **The released contract is a committed snapshot, not the live schema.**
  `shared/openapi/v1.json` is produced from `create_app().openapi()` without a
  server and committed at release time. CI and the test suite compare the
  current schema against that file, so an endpoint can be removed in a branch
  and still fail the check. Additive changes pass without updating the
  snapshot, which keeps the diff meaningful.
- **The checker lives in `erp_shared`.** `shared/py/erp_shared/api_compat.py`
  is pure standard library, so the CI script, the backend test and the shared
  unit tests run exactly the same rules. It resolves local `$ref`/`allOf`
  pointers and reports endpoint, parameter, request-body, response, field,
  type, enum, union and constraint changes inside `/api/v1` only.
- **Two snapshots enforce the deprecation window.** `--write` rotates the
  existing baseline to `shared/openapi/v1.previous.json` before writing the new
  one. A removed operation or field is accepted only when it carried
  `deprecated: true` in *both* snapshots, i.e. it survived two releases. Without
  a previous snapshot the first removal is still refused.
- **Only release managers run `--write`.** Running it in a feature branch would
  move the baseline and hide a breaking change from the guard. The README says
  so explicitly, and the generated snapshot is reviewed like any other release
  artefact.
- **Request constraints are checked directionally.** Raising `minimum` or
  `minLength`, or lowering `maximum` or `maxLength`, is breaking for a request
  and reported; the same change in a response is not. Widening a request is
  always allowed.
- **System routes stay outside the policy.** `/health`, `/ready` and other
  non-`/api/v1` paths are ignored by the checker; the versioning policy and the
  snapshot cover the school API surface only.

## 2026-11-18 — P1-SEED demo data

- **Every mutation goes through the audited service path.** Earlier seed code
  inserted `SampleNote` and school translations directly. The seed now calls
  `set_entry`, `import_theme`, `set_setting` + `record` and the `sample.notes.create`
  action, and records the role assignments it makes. A fresh demo instance
  therefore starts with real activity history (role grants, role-permission
  change, i18n creates, theme imports, a settings update and a note) instead of
  an empty audit page, and the entries hash-chain exactly like live changes.
- **Audit history is generated only when something changes.** Re-running the
  seed is a no-op: role assignments are compared before replacing, translation
  `set_entry` audits only real edits, themes are imported only when missing or
  drifted, and the sample setting/note are skipped when already present.
  Running the seed twice leaves every table count and the audit count unchanged.
- **The demo-only `limited` role is verified, not recreated blindly.** Its
  permission set is compared with `DEMO_LIMITED_PERMISSIONS`; only a difference
  triggers the bulk replace and the `rbac.role.permissions` audit entry. All
  shipped default roles still come from `ensure_default_roles`, so §1 accounts
  always map to the documented role keys.
- **Four school-layer overrides and two example themes.** The overrides cover
  the dashboard subtitle, the app tagline, the welcome line and the language
  hint, which exercises `default < central < school` on more than one key. The
  `highlands` and `sunset` themes reuse the shipped token map with different
  primary/accent colours and radii; they pass the same WCAG contrast checks as
  any imported theme, stay selectable, and do not replace the builtin default,
  so first-run theme behaviour remains predictable.
- **Seed scripts are not a privileged back door.** They still talk to the same
  services and the same license verification path as the application, and the
  seed refuses `APP_ENV=production`.
- **The seed registers every mapper before creating tables.** `create_all()`
  only creates tables whose models have been imported. The seed imports
  `app.main` (which imports every router and therefore every model) before
  `Database.create_all()`, so the demo database has `notification_templates`,
  `jobs`, `files` and the rest. Without this, the seed succeeded but the first
  request that touched notifications failed with "no such table".

## 2026-11-18 — P2-01 academic structure and scope

- **Scope keeps the published numeric contract.** `academic_scope.first_level`
  and `last_level` remain integers 0–12 (already part of the released OpenAPI
  via the setup request): `0` is the kindergarten bucket and `1`–`12` are the
  matching grades. Grade levels therefore carry a `scope_level` used only for
  filtering. A school that runs `KG1`–`KG3` selects `0`; a Grade 1–5 school
  selects `1`–`5`, and every listing endpoint (levels and stage membership)
  filters on it. Changing the settings type to level keys would have been a
  breaking API change.
- **Catalog editing is additive and reversible.** The shipped `KG1`–`Grade 12`
  levels and five stages are created once by a new module bootstrap hook and
  marked `is_starter=True`, `is_verified=False` so setup screens can ask the
  school to verify them. They are ordinary rows: renameable, re-scopable,
  deactivatable and soft-deletable. A deleted starter row is not recreated on
  the next boot because the bootstrap lookup includes soft-deleted rows.
- **Deleting a stage or level keeps membership links.** Soft-deleting a stage
  leaves its `academics_stage_levels` rows in place, so restoring it brings its
  levels back intact. Soft-deleting a level hides it from stage listings (the
  join only sees live levels) and restoring it makes it reappear. Hard deletion
  is still never used; replacing a stage's level list is the only place where
  association rows are deleted (the same pattern as role permissions).
- **Module starter data uses a manifest hook.** `ModuleManifest.bootstrap` lets
  a module provide an idempotent seed callable that core bootstrap (and the demo
  seed) runs inside the shared session. This avoids `core` importing `modules`,
  keeps the zone boundaries intact, and gives later modules (curricula,
  templates) a supported place for starter data.
- **Scope changes are atomic and audited.** `PUT /academics/scope` validates the
  order and that at least one active level exists in the range, writes the two
  core settings in an order that never leaves the model invalid, and writes one
  `academics.scope.update` audit entry. Repeating the same scope is a no-op.

## 2026-11-18 — P2-02 academic years and terms

- **One open academic year at a time.** A year moves `draft → open → closed`.
  Opening a second live year is rejected with a clear `409` until the first is
  closed, so "current year" is unambiguous for enrollment, fees and reports.
  Reopening a closed year is allowed and audited; a closed year is immutable
  until reopened.
- **Closing a year closes every term in it**, including terms that never
  opened. Terms are then explicitly reopened if a correction window is needed,
  which keeps the year result closed while allowing a controlled exception.
- **The term system is snapshotted per year.** `academic_scope.term_system`
  (semester = 2, quarter = 4) is a core setting used when a year is created.
  Changing the setting later only affects new years; existing years keep their
  term count because results and document templates address terms by number.
  The term count is fixed at creation and terms are never added or removed.
- **Dates are stored in GC and displayed in EC or GC.** `DATE` columns keep
  ordering and reporting independent of the display preference. Responses add
  `*_ec` values (`YYYY-MM-DD` Ethiopian) and `*_display` labels produced by the
  shared Ethiopian calendar using `school_profile.calendar` and
  `school_profile.default_language`. No date is stored twice.
- **Year deletion is for drafts only.** Deleting an open or closed year would
  hide history, so the API requires closing it and returns `409` otherwise.
  Deleting a draft is a soft delete and keeps its terms, so restoring the year
  brings the terms back intact.
- **Term editing follows the year state.** Names and dates can be edited while
  the year is a draft or open; a closed year rejects edits. Term dates are
  validated to stay inside the year, in chronological order and non-overlapping.

## 2026-11-18 — P2-03 subjects, level assignments, subject groups and sections

- **Subjects are school-global, not per year.** A subject (name, code, stream)
  is a stable catalogue entry reused across years. What changes per year is the
  *offering*: `academics_level_subjects` says which subjects a level studies,
  and sections sit per year and level. This keeps historical results attached
  to one subject row instead of a copy per year.
- **Association tables are replaced, not versioned.** `academics_level_subjects`
  and `academics_subject_group_members` are pure join tables with no own
  identity or history. `PUT`/`PATCH` replaces the full set for its parent in one
  audited operation; removed rows are hard-deleted because the audit entry
  records the previous and new sets. Soft delete is still used everywhere a row
  carries meaning of its own (subjects, groups, sections).
- **Homeroom teacher validation is deferred to Phase 3.** `sections.homeroom_user_id`
  is already a foreign key to `users` and only active users can be assigned, but
  the "must be a staff member of this school" rule needs Phase 3 staff records.
  The FK plus active-user check is the strongest guarantee available now; the
  stricter rule will be added when staff profiles exist.
- **Section listings honour the school scope by default.** A user with
  `academics.view` sees sections inside the configured level range; passing
  `scope=all` requires `academics.manage` and shows every level. This mirrors
  the grade-level behaviour and stops a primary coordinator from curating
  secondary sections by accident.
- **Closed years freeze section mutations.** Sections belong to a year, so
  create/update/delete/restore reject a closed year exactly like term edits. The
  section can still be read, and reopening the year restores editability.
- **Capacity is an integer count of seats.** It is nullable (capacity unknown)
  and validated non-negative; occupancy is derived from enrollments in Phase 2
  later tasks rather than stored twice.

## 2026-11-18 — P2-04 curriculum profiles

- **A profile bundles what exists today and grows later.** This phase stores the
  term system plus subjects per level (with the same integer credit as level
  assignments). Mark-structure templates, grade scales, promotion rules and
  document templates join the same profile in their own phases; the profile id
  on a year is the stable link they will use.
- **Shipped profiles are editable starter data.** The bootstrap creates the
  three templates only when their code is missing (including soft-deleted
  lookups, so a deleted row is not resurrected). Every field, subject and credit
  can be edited, and a school can duplicate any profile and change the copy.
  Shipped profiles cannot be deleted because losing a baseline template is hard
  to undo; they can be deactivated instead. Custom profiles are soft-deletable
  and restorable.
- **Applying is preview-then-confirm.** `POST …/apply` with `confirm=false`
  returns added, removed and credit-changed counts plus affected level codes
  without writing anything, so the UI can show the impact before touching the
  school's subject map. `confirm=true` performs the replacement and records one
  `academics.curriculum.apply` audit entry on the year.
- **Applying replaces the in-scope level-subject map.** Subjects per level are
  school-global, so the profile is the new map for every level in the school's
  scope: subjects absent from the profile are removed, not merged. Out-of-scope
  and inactive levels are untouched, and inactive subjects are skipped and
  reported. The chosen year records `curriculum_profile_id`, which is the
  provenance of the map from that year forward.
- **Term systems cannot be retrofitted.** A year snapshots its term system at
  creation (P2-02). Applying a semester profile to a quarter year is rejected
  with `409`; the supported path is to create the year with the profile, which
  adopts the profile's term system, term count and starting subjects in one
  audited operation. Re-applying the same profile is a no-op.
- **Closed years are frozen.** Applying a profile to a closed year is rejected
  even for a preview, matching the rule for sections and term edits.

## 2026-11-18 — P2-05 academics UI

- **Module bundles are prefixed once, at load time.** A module's `i18n/en.json`
  ships bare keys (`"nav"`, `"perm.view"`) while the manifest and every module
  router reference them as `academics.nav`, `academics.perm.view`. The shared
  `TranslationLoader` now prefixes non-core bundles with their namespace when
  stacking messages, so both server-side action labels and web screens resolve
  the same key without duplicating the bundle under two names.
- **The setup wizard is a checklist inside `/academics`, not a separate flow.**
  The steps (scope, curriculum, year, subjects, sections) can be revisited in
  any order as the school grows. The checklist shows live completion from the
  real queries and each step opens the same tab used for day-to-day editing, so
  there is one implementation per screen and no divergent "wizard" state.
- **One route, tabbed panels, permission-aware controls.** `/academics` requires
  `academics.view`; every mutating control is hidden without
  `academics.manage`. The scope panel only requests `scope=all` when the user
  can manage, so a viewer sees exactly the scoped catalogue the API allows.
- **Scope pickers show level names, not synthetic prefixes.** The API keeps the
  integer `scope_level` for ordering and filtering, but the UI displays the
  school's own level names (which already include "KG"/"Grade"), avoiding a
  hard-coded label that drifts from renamed levels.
- **The curriculum screen is preview-gated.** "Apply profile" stays disabled
  until a preview has been fetched and the term systems match; the preview card
  shows added/removed counts and affected levels before the confirm call.
- **Frontend tests stub `fetch` at the API boundary.** New Vitest suites render
  the real routes with a shared mock-session/route helper, asserting request
  paths and bodies for scope, year, subject assignment, section and curriculum
  mutations rather than mocking React Query internals.

## 2026-11-18 — P2-06 students module

- **A student is a shared person plus a profile.** Names, date of birth, phone,
  photo and person-level custom fields stay on `persons`; the students module
  adds `student_profiles` keyed by `person_id`. One live profile per person, and
  one live student number, are enforced by partial unique indexes. Deleted
  numbers can be reused; restoring a student therefore re-checks the number and
  returns `409` if another live student took it.
- **Registration is one transaction.** `register_student` creates the person,
  profile, optional enrollment, guardians and medical record, flushes them
  together and commits once. `create_person`/`update_person` accept
  `commit=False` for this flow; `prepare_person` exposes the validation and
  duplicate-warning step without writing.
- **The person input model moved to `core.people.schemas`.** Students, guardians
  and later admissions/staff screens all need the same three-part-name payload,
  so `PersonInput` is shared rather than re-declared per module. It now carries
  `photo_file_id`.
- **Academic placement is referenced, not duplicated.** Enrollments store
  `year_id`, `level_id` and `section_id` as plain UUID columns without
  cross-module foreign keys. The students module `depends_on = ["academics"]`
  and resolves labels through academics service functions; it never imports
  academics tables. A closed year, an inactive level/section, and a section that
  does not belong to the chosen year+level are rejected at write time.
- **Statuses are an explicit vocabulary.** `applicant`, `active`, `promoted`,
  `repeating`, `transferred_out`, `withdrawn`, `graduated`, `alumni`.
  Registration defaults to `active` when an enrollment is supplied and
  `applicant` otherwise; promotion rules arrive in P2-11. Status values are
  validated in the schema and again in the service for action/API parity.
- **Guardians are a many-to-many link to persons.** A guardian can be an
  existing person (`person_id`) or created inline (`person`), never both. One
  live link per student+person, at most one primary contact per student (the
  service clears the previous primary in the same audited operation), and a
  student cannot be their own guardian. Links are soft-deleted and restorable.
- **Medical data has its own permission pair.** Reading requires
  `students.medical.view`; writing requires `students.medical.manage`. The
  student detail endpoint only includes medical data when the caller can view
  it, so `students.view` alone cannot leak health information. Separate routes
  and actions (`students.medical.get` / `students.medical.update`) make the
  boundary explicit in the route × role matrix. Registration accepts a medical
  block only when the caller also holds `students.medical.manage`, so
  `students.manage` alone cannot create health records through the front door.
- **Student documents are scoped by ownership.** Files uploaded through
  `POST /students/{id}/documents` are stored with
  `owner_entity_type="student"` and the student id. Listing and deleting go
  through the students API and require `students.view`/`students.manage`; a file
  owned by another student returns `404` rather than revealing its existence.
  The general file list now excludes soft-deleted rows.
- **Search folds both scripts.** Free-text search normalizes Geez homophones and
  matches every term against the person's normalized search name, plus a
  substring match on the student number. List filters (`status`, `year_id`,
  `level_id`, `section_id`) use an enrollment `EXISTS` subquery so a student is
  returned once even with several enrollments.
- **Default role grants.** Registrar gets students view/manage and medical
  view/manage; director gets students view/manage and medical view; academic
  head gets students view; homeroom teacher gets students view. These are
  starting points and remain editable through RBAC.

## 2026-11-18 — P2-07 student number generator

- **Numbering is module settings, not a separate screen.** The students module
  declares `StudentSettings.numbering` with `format`, `scope` and `start`. The
  Settings page renders it from the typed schema like every other module, and
  changes are validated and audited by the existing settings API. Defaults are
  `STU-{year}-{seq:04d}`, one sequence per academic year, starting at `1`.
- **The format grammar is deliberately small.** A template combines literal
  text with `{year}` and exactly one `{seq}` or `{seq:0Nd}` zero-padded token.
  Literals are limited to letters, digits, spaces and `- _ . / # ( )`; unknown
  tokens, stray braces, multiple `{seq}` tokens and widths above 39 are
  rejected. Rendered numbers are re-checked against the 40-character column as
  the sequence grows, so a valid template cannot silently overflow the column.
- **Year scope requires `{year}`.** Student numbers are globally unique, so a
  per-year counter without a year token would issue the same number in two
  years. The settings model rejects that combination at save time instead of
  letting registration fall into conflict retries.
- **The sequence bucket is the enrollment year, then the open year.** Preview
  and registration accept an optional academic year; registration passes the
  enrollment year when there is one. Otherwise the open year is preferred, then
  the most recently started year, and finally the calendar year so a school can
  register applicants before creating its first academic year. Year-scoped
  keys are `year:<uuid>`; a global sequence uses one `global` key. Changing the
  format or start value never rewrites an existing bucket: only later numbers
  in that bucket use the new settings.
- **Allocation is a single atomic upsert.** `student_number_sequences` holds one
  row per scope. Both SQLite and PostgreSQL use `INSERT … ON CONFLICT (scope)
  DO UPDATE SET value = value + 1 RETURNING value`, so concurrent registrations
  serialize in the database and can never receive the same number. The
  allocation commits in its own short transaction before the rest of
  registration. A failed registration therefore leaves a gap, which is
  acceptable; reusing a number is not. If a manually typed number already
  occupies a generated candidate, registration skips that candidate (up to ten
  times) and reserves the next one.
- **Previews do not reserve.** `GET /students/number-preview` and the
  registration preview return the next candidate without touching the
  sequence, so two open forms may see the same number; the create call remains
  authoritative. Preview requires `students.manage`, matching registration.
  The action `students.numbers.preview` exposes the same behaviour to the AI
  layer.
- **Explicit numbers remain first-class.** Registration still accepts a typed
  number (trimmed); omitting it or sending a blank string generates one. The
  unique live index remains the final guard and returns `409` on a duplicate,
  including when restoring a soft-deleted student.
- **Registration, not the counter, is the audit record.** The counter is
  internal bookkeeping and is deliberately not soft-deleted or audited;
  `students.register` records the assigned number in the before/after state.
  Settings changes remain audited by the settings module.
- **Student error keys now use the module namespace.** The web loads module
  bundles under `<module>.<key>`, so `error.students.*` keys could never
  resolve. The students module now raises `students.error.*` keys, its bundle
  gains the new numbering errors, and the web loads the `students` namespace.

## 2026-11-18 — P0-19b web design foundation

- **One kit, one stylesheet.** `shared/ts/ui-web` ships React components plus
  `src/styles.css`. Components emit `ui-*` classes; the stylesheet owns every
  value and reads only tokens. Both web apps import the stylesheet once, so a
  component added to the kit cannot drift between school web and controller
  web. Local `components/ui/*` files re-export the kit, keeping existing imports
  working while the feature screens migrate.
- **Tokens in CSS variables, scales in `@erp/tokens`.** Spacing (4/8/12/16/24/
  32/48/64), type (12–30), weights (400/500/600), line heights, radii, shadows,
  breakpoints, layout sizes and touch targets are declared in
  `shared/ts/tokens` for JS consumers and mirrored as `--*` variables in the kit
  stylesheet. A school theme may change colour/radius/font tokens only; layout
  and spacing are fixed so a community theme cannot move things.
- **Fonts are bundled, with tabular numerals.** Inter Variable (OFL, licence
  file next to the font) carries Latin text; Noto Sans Ethiopic is kept for
  Ge'ez. `font-variant-numeric: tabular-nums lining-nums` (`.ui-num`) is applied
  to table figures and money. Mobile uses the platform system sans (SF/Roboto)
  because Expo Go cannot bundle a variable font reliably at runtime; the metrics
  are close enough for the shared scale and the decision is revisited if the
  owner wants Inter on mobile too.
- **Kilobytes over pixel-perfect novelty.** Dates in the reference screens are
  illustrative data, not formatting logic: every rendered date still goes
  through the calendar layer and every amount through `formatSantim`. Demo rows
  live in the page, translated text comes from `t()`.
- **Lint replaces review-by-memory.** `design/no-hardcoded-style` rejects hex /
  rgb / hsl / oklch literals, arbitrary Tailwind values (`p-[13px]`) and
  palette colours (`bg-slate-100`) in web TSX; the i18n rule keeps banning
  literal UI text. Escapes exist but are tokens: `.ui-min-w-28…56` for wide
  tables, `.ui-float-panel` for the assistant, `.ui-mobile-only` /
  `.ui-desktop-only` / `.ui-wide-only` for responsive visibility.
- **Kit CSS is unlayered on purpose, with one gotcha.** Tailwind v4 puts
  utilities in `@layer utilities`, so an unlayered kit rule wins over a
  utility on the same property. That is desirable for component styling, but it
  means visibility of kit components must use kit classes rather than
  `md:hidden` (seen on the top-bar menu button). Layout of plain `div`s can
  still use Tailwind utilities.
- **Top-bar density by width.** Desktop shows identity, language, school theme
  picker, light/dark and sign out. Tablets keep identity, language, light/dark
  and sign out (the theme picker lives in Settings → Themes). Phones keep only
  identity and the menu button; language, theme, mode and sign out move into
  the navigation drawer, which has a tap-away scrim and closes on Escape.
- **Review artefacts.** `docs/review/p0/` holds 1440/768/390 × light/dark ×
  en/am screenshots of the list, form, dashboard, shell and the phone drawer;
  the self-review entry is in `docs/OWNER_REVIEW.md` and the checklist is
  `docs/UI_CHECKLIST.md`.

## 2026-11-18 — P0-21b mobile design foundation

- **The native kit mirrors the web kit.** `owner/mobile/src/ui` exports the same
  component vocabulary (`Button`, `Field`, `Card`, `ListRow`, `BottomTabs`,
  `Sheet`, `Toast`, `Badge`, `Skeleton`, `EmptyState`, `ErrorState`, `SaveBar`)
  built from `@erp/tokens`. Spacing, type and touch sizes are imported from the
  shared scales; colour and radius come from the active school theme, so a
  community theme cannot move a layout. `oklch` tokens are converted to sRGB for
  React Native in `nativeTheme.ts`, which is also what keeps web screenshots
  faithful to the native colours.
- **Bottom tabs are capped at five including “More”.** A school can have more
  modules than that, so the first four fit in the bar and the rest live in a
  sheet with the language, theme and sign-out controls (the same information
  architecture as the phone web drawer). Safe-area insets pad both the tab bar
  and the sheet.
- **Badge tones use filled semantic pairs.** `success` is primary on
  primary-foreground, `warning` is accent on accent-foreground, `danger` is
  destructive on destructive-foreground. The earlier “tinted secondary” version
  measured 4.42:1 for success in dark, just under WCAG AA, so the tokens are used
  as designed instead of mixed.
- **Forms scroll under a sticky action bar.** `SaveBar` sits outside the
  `Screen` scroll view and pads for the bottom safe area, so the primary action
  never scrolls away on a long form.
- **Screenshots come from Expo web at phone sizes.** No emulator or device is
  available on this host (OWNER_ACTIONS #6), so `owner/mobile` renders through
  the Expo web target at 390×844 and 430×932 for review. To make that possible,
  `src/storage/secureStorage.ts` wraps `expo-secure-store` with a `localStorage`
  fallback on web; the native build still uses the Keychain/Keystore, and web is
  not a supported production target for the app. The capture spec is
  `e2e/tests/design-mobile-screenshots.spec.ts` (guarded by
  `RUN_MOBILE_SCREENSHOTS=1`).
- **Reference data is a fixture, formatting is real.** Rows and the request id
  are demo data, but dates go through `@erp/calendar` (`formatDual`, both
  calendars, localized) and the money figure through `formatSantim` with the
  unit in the card label.

## 2026-11-18 — P1-27 UI quality gate

- **The gate is split by cost and by what it needs.** `e2e/tests/ui-quality-gate.spec.ts`
  runs the axe sweep, the static state check and the theme checks in the normal
  e2e suite; the 48-shot screenshot matrix (4 key screens × 1440/768/390 ×
  light/dark × en/am) plus the long-Amharic captures stay behind
  `RUN_UI_GATE_SCREENSHOTS=1`, like the P0 screenshot specs, so a routine run
  does not rewrite review artefacts. Captures land in `docs/review/p1/`.
- **State coverage is checked at the source, not by driving every branch.**
  Every data screen must reference `LoadingState`, `EmptyState` and `ErrorState`
  from `@erp/ui-web`; the list lives in `e2e/lib/ui-gate.ts`. Driving each
  screen into an empty or failed backend response would need per-screen API
  stubs and would still miss the branch that matters on a real request. A
  fixture screen that forgets its empty state is committed under
  `e2e/fixtures/ui-gate/` and the gate proves it fails.
- **Empty and error states are now part of every data screen, not just the
  dashboard.** The migration also made the request id visible next to the retry
  action through `requestIdOf()` in `school-erp/web/src/lib/errors.ts`, and
  added the missing `EmptyState`/`ErrorState` branches to the academics panels.
- **A theme can change colour and type, never structure or CSS.** The gate
  previews a recoloured community theme (accepted) and applies its tokens to
  `:root`; heading size, card padding, sidebar width and body size must not
  move. Token values are also written into a stylesheet, so the backend now
  rejects `;`, `{`, `}`, newlines, `</` and `/*` in any token with an
  `unsafe_value` issue. A deliberately low-contrast theme must come back
  `valid: false` with a `contrast` issue.
- **768 px needed a real layout fix.** The Users table is wider than the
  available card, and its grid item expanded the page instead of scrolling the
  table. `min-w-0` on the card and grid keeps the overflow inside the table
  wrapper, which is what the checklist requires.

## 2026-11-18 — P2-08 students UI

- **Student photos have their own endpoints.** `POST /api/v1/students/photos`
  (before the record exists, so a new registration can attach a portrait) and
  `GET /api/v1/students/{id}/photo` are guarded by `students.manage` /
  `students.view` instead of `files.upload` / `files.view`. The shipped
  registrar and academic-head roles hold the student permissions but not the
  file permissions, so reusing the generic file routes would have hidden photos
  from exactly the people who maintain student records. The uploaded row is
  still a normal `StoredFile`; the profile only stores `photo_file_id`.
- **Saved views are a client preference, not a backend model.** The list keeps
  named filter sets in `localStorage` under `erp.students.saved_views`. The task
  asks for saved views on one screen, and a per-user server model would be a new
  table, route and permission for a personal convenience. Moving them to the
  server later changes only `savedViews.ts` and the load/save calls.
- **`DEMO_MODULES` now includes `students`.** The module ships `default_enabled
  = True`, but the demo license is an explicit signed list, so the seeded school
  would otherwise not show the students menu. `tests/test_seed.py` asserts the
  licensed and enabled lists still match the constant.

## 2026-11-18 — P2-09 admissions module

- **A draft academic year can take applications; only a closed year is
  refused.** `AcademicYear.status` starts as `draft` and becomes `open` through
  an explicit office step, so requiring `open` made intake impossible in the
  normal setup flow and contradicted how student enrollment already behaves.
  `_resolve_year` prefers the open year when the caller omits `year_id`, then
  falls back to any non-closed year, and refuses `closed` with
  `admissions.error.year_closed`.
- **Conversion writes the auto-assigned section back onto the application.**
  The applicant may arrive without a section and be placed by the capacity
  rule at conversion time. Storing `row.section_id = enrollment.section_id`
  means the application and the student record agree afterwards, and a second
  conversion attempt cannot silently choose a different section.
- **Required admission custom fields are enforced even when `custom` is
  omitted.** Passing `{}` to the custom-field validator on create means a
  required field always fails with `error.custom_field.invalid`, instead of
  being skipped when the client simply leaves the object out. Unknown keys are
  still rejected because the same validator runs.
- **Guardian accounts may only receive the configured low-privilege role.**
  Accounts use `form.guardian_role_key` (default `parent`), never a role
  supplied by the caller. A missing role is reported as
  `guardian_role_missing`, and a guardian without an email as
  `guardian_email_missing`, rather than creating a half-working account. The
  generated password is random, `must_change_password` is set, and the
  invitation is a normal single-use reset link.
- **An existing user with the guardian's email is linked, not duplicated.**
  The application guardian stores `account_user_id` and the conversion returns
  the `existing_guardian_account` warning. Creating a second account for the
  same email would either fail the unique constraint or give one person two
  logins, so linking is the only coherent choice.
- **`ActionContext` gained optional `request` and `settings`.** Conversion sends
  the guardian invitation through the same recovery path as the auth router,
  which needs the request for the client IP and the guest settings for the
  reset lifetime and base URL. The AI layer constructs an `ActionContext`
  without them, so those best-effort emails are skipped there while every
  database effect still happens.
- **Conversion goes through students' public helpers.** `student_id_for_person`,
  `student_number_for`, `create_profile_for_person` and `section_occupancy`
  live in `modules/students` so admissions never imports the students tables or
  writes a profile directly. The helpers keep the profile audit entry
  (`students.profile.create`) and the number allocation in the students module.
- **Admissions is a licensed, default-enabled module that depends on
  `academics` and `students`.** The module gate therefore refuses to disable
  students or academics while admissions is on; the existing module-gate tests
  now switch admissions off first. `DEMO_MODULES` includes `admissions` so the
  seeded demo license exposes the menu.

## 2026-11-18 — P2-10 admissions UI and public application page

- **The public page is a separate route at `/apply`, outside the signed-in
  shell.** A guardian without an account must be able to reach it, so it is
  registered next to `/login` and `/reset-password` instead of under
  `RequireAuth`. The server still gates it on the `admissions` module being
  licensed and on `form.public_enabled`, and the page renders a "closed" state
  when either is false rather than an error.
- **A signed, short-lived form token carries the submit window.** `GET
  /admissions/public/form` issues a JWT (`type=admissions_public_form`, 60
  minutes) carrying its issue time. The submit route requires it, so the
  server can enforce `form.public_min_seconds` without trusting a client
  timestamp, and a form scraped once cannot be replayed forever. The token is
  signed with the instance secret and is not tied to a session.
- **Bot defence is layered and independent of the UI.** A hidden `website`
  honeypot field rejects naive form fillers before any database work, a
  per-IP `SlidingWindowLimiter` (`form.public_rate_limit`, default 5/hour)
  blunts scripted repeats, and the minimum fill time blocks instant posts. The
  honeypot input is `aria-hidden` and `tabIndex={-1}` so it never appears in the
  accessibility tree or the tab order.
- **Public submissions are ordinary applications with a system actor.** They go
  through `service.create_application` with `source="public"` and a
  `Principal(actor_id="public", actor_type="system", via="web")`, so numbering,
  audit entries, custom-field validation and duplicate warnings behave exactly
  as for the office. The response is only `PublicApplicationOut`
  (number, name, status, year and level): returning guardians or duplicate
  warnings would leak personal data to an unauthenticated caller.
- **The public page only exposes fields a guardian may see.** The form calls
  `definitions_for` with a permission-less principal, which drops definitions
  that set `visible_roles`. The client passes those definitions into
  `CustomFieldsForm` directly (new optional `definitions` prop) so the public
  page never calls the authenticated `/custom-fields` endpoint.
- **Public guardians are always new people.** `PublicGuardianInput` carries a
  person description only, never `person_id`, so a public post cannot link an
  existing person or account. Account creation stays an office decision made at
  conversion.
- **The office UI keeps one page per step.** `/admissions` lists and filters;
  `/admissions/new` and `/admissions/:id/edit` share the form; `/admissions/:id`
  holds the decision, conversion and documents. Duplicate warnings come from
  `POST /admissions/preview` before the create call, so the office sees "save
  anyway" without a second dialog component. Editing is offered only in the
  statuses the service accepts (`applied`, `reviewed`, `test`, `offered`).
- **Guardians are editable only while taking the application.** The service has
  no guardian update route, so the edit form explains that guardians are managed
  from the student record after enrolment instead of pretending to edit them.

## 2026-11-18 — P2-11 promotion and transfer

- **One planner serves both preview and apply.** `progression_service._plan`
  resolves the next in-scope level, the matching target section and every
  warning; `preview_promotion` only serialises its rows, while
  `apply_promotion` re-runs it and writes the result. The two screens therefore
  cannot disagree about which students move or where.
- **Defaults are deterministic.** A student below the last in-scope level is
  `promote`; a student in the last level is `graduate`. A manual exception may
  override this with `promote`, `repeat`, `graduate` or `skip`. `skip` leaves
  the profile status untouched, so a mistaken row in a batch has no side effect.
- **Missing target sections are warnings, not blocks.** Sections have no id
  continuity across years, so the planner carries the source section `code`
  over to the target level. If that code is absent the student is enrolled in
  the target level without a section and the row shows
  `students.progress.warning.section_unmapped`; the office can edit the
  enrollment afterwards. A target section that was explicitly supplied but
  belongs to another year or level is blocking, because the request itself is
  inconsistent.
- **Already-enrolled students are skipped.** Running a batch twice must not
  duplicate placements, so any student with a live enrollment in the target
  year becomes `skip` with
  `students.progress.warning.already_enrolled`, regardless of their exception.
- **Profile statuses record the outcome.** `promote` sets `promoted`, `repeat`
  sets `repeating`, and `graduate` sets `graduated` with `exit_date` and
  `exit_reason`. A capacity warning (`section_full`) never blocks a batch: the
  school may deliberately overfill a section, and the office decides.
- **Status transitions are explicit.** `transfer_out`, `withdraw` and
  `graduate` are allowed from `active`, `promoted` and `repeating`; `alumni`
  only from `graduated`; `reinstate` only from `transferred_out` or
  `withdrawn`. `transfer_out` and `withdraw` require a reason. Graduation is
  additionally checked against the latest enrollment and the highest in-scope
  level, so the single-student route cannot bypass the bulk rule.
- **Audit rollback restores both halves of a promotion.** The
  `student_progression` reverter restores the before-status and exit fields and
  soft-deletes the enrollment created by that same entry. It compares the
  before and after enrollment ids, so a status change that did not create an
  enrollment never deletes an unrelated one.
- **The transfer-out certificate is deferred to Document Studio.** The
  certificate is a printable artifact owned by the documents module in Phase 5;
  Phase 2 records the transfer-out status, exit date and reason so the template
  can be generated when that module lands.
- **Promotion rules wait for Phase 4 through a resolver hook.** `_plan` accepts
  an optional `rule_resolver` callable that receives a candidate and returns an
  action. The default resolver encodes only the next-level/final-level rule;
  P4-03 will pass the assessment rule engine through the same hook without
  changing the HTTP surface.

## 2026-11-18 — P2-12 mobile students

- **The mobile directory is the same API, not a second read model.** It calls
  `GET /api/v1/students` with the shared `q`, `status` and cursor parameters, so
  the web and mobile screens cannot drift on filtering or page size. A search
  only issues a request when the user submits it, and "Load more" appends the
  next cursor page while keeping the first page visible.
- **Profile visibility follows the permission, not the payload.** The medical
  card renders only for `students.medical.view`; the backend already omits the
  medical object for callers without that permission, so hiding the card is a
  presentation guard rather than the security boundary.
- **Registration is online only by design.** The phone posts the preview and the
  create request directly to the school server and surfaces
  `students.error.network` when it cannot reach it; there is no offline outbox
  for student registration. Phase 3 adds offline entry only for attendance.
- **Preview then confirm.** One tap runs
  `POST /api/v1/students/register/preview`. Without duplicate warnings the app
  immediately creates the student; with warnings it shows the candidate names
  and generated number and changes the action to "Register anyway", matching
  the web dialog's confirm step. This keeps one network round trip in the
  common case without silently creating a likely duplicate.
- **Name validation mirrors the backend.** A script (Latin or Amharic) must be
  either empty or complete across given, father and grandfather names. The
  screen rejects a partial script before calling the API, so the user does not
  have to decode a server validation error.
- **Enrollment stays optional, but all-or-nothing.** Leaving the year and level
  empty registers an applicant. Choosing one without the other is rejected as
  `students.register.enrollment_incomplete`; sections additionally require both
  and are loaded only after a year and level are chosen.
- **Module translation bundles are namespaced on mobile.** The translation
  loader prefixes non-core bundles with their namespace (`students.title`,
  `students.nav`), matching the web loader and the navigation keys returned by
  `/auth/me/navigation`.

## 2026-11-18 — P2-13 student domain events

- **Events live in `modules/students/events.py`.** Registration, admissions
  conversion, enrollment and promotion all call the same three payload
  builders, so the event names and fields cannot drift between entry points.
- **`student.admitted` means a student profile was created.** Direct
  registration emits it from `register_student`; admissions conversion emits it
  from `create_profile_for_person`. It carries the student id, number, person,
  status and admission date; the enrollment that may follow is described by its
  own event rather than being duplicated in the admission payload.
- **`student.enrolled` is owned by `create_enrollment`.** Registration,
  admissions conversion, manual enrollment and promotion/repeat all go through
  that service, so one hook covers every placement. The payload identifies the
  enrollment, year, level, section, roll number and status.
- **`student.promoted` records the year-end outcome.** It is emitted once per
  non-skipped promotion row and carries an `action` of `promote`, `repeat` or
  `graduate` plus the source and target years/levels/sections. A skipped row is
  a no-op and emits nothing, so automation cannot mistake it for a move.
- **Events join the caller's transaction.** The outbox row is written in the
  same commit as the student change, and preview endpoints emit no events.
  Audit rollback restores the student state but intentionally does not retract
  historical outbox rows, because an event records that something happened even
  if it was later corrected.

## 2026-11-18 — P2-SEED demo academic year, roster and staff

- **The demo school is narrowed to kindergarten through Grade 8 before the
  2026-2027 year is created.** Scope is written through the audited
  `update_scope` service first, so applying the `ethiopian_national` profile
  maps only the levels the demo actually teaches and the Grade 9–12 starters
  never appear in the year's subject map.
- **One section per KG level and two (A/B) per grade.** That gives 19
  sections across 9 levels. The plan lives in `DEMO_SECTION_PLAN` and is shared
  by the seed and its test, so the expected count cannot drift.
- **The roster is deterministic and explicitly numbered.** `STU-2026-0001` to
  `STU-2026-0060` are generated from a fixed name pool; matching on the number
  is what makes a re-run a no-op. Numbers rather than generated sequences are
  used because `register_student` would otherwise advance the school's
  numbering sequence on every seed run.
- **The first two students are siblings.** They share the same father and
  mother guardians, and the father is the person behind `parent1@demo.school`,
  so the parent account already used by the demo has two children to view.
  Every other guardian is a seeded person with a deterministic email.
- **Staff placeholders are `Person` rows, not users.** The staff module arrives
  in Phase 3; each placeholder reuses the email of an existing demo user
  (`director@`, `teacher1@`, …) so the module can link the person to the
  account later without renaming. Homeroom references reuse those teachers.
- **Every write goes through an audited service function.** Scope, year,
  sections, people and student registration are all created via
  `update_scope`, `create_year`/`open_year`/`open_term`, `create_section`,
  `create_person` and `register_student`, so a fresh demo instance carries a
  realistic, verifiable activity history instead of direct inserts.
- **The demo year is opened with its first semester.** The seed only opens the
  year when no year is current and only opens term 1 when no term is open, so
  re-running never disturbs a year an operator has since closed or advanced.

## 2026-11-18 — P3-01 staff module

- **Staff numbers use their own global sequence.** `STF-{year}-{seq:04d}` is
  rendered by `modules/staff/numbering.py` and reserved with one dialect
  upsert, so two simultaneous registrations cannot receive the same number.
  This is deliberately separate from the configurable student numbering: a
  staff number is not a school policy knob in phase one, and an explicit
  number is always accepted so imported records keep their identifiers.
- **Departments and positions are deactivated, not deleted.** They carry an
  `is_active` flag and appear only with `include_inactive=true` once retired.
  A position cannot be assigned while inactive, and an inactive department
  cannot receive positions. Staff profiles, contracts and qualifications use
  the standard soft-delete/restore path because their history must remain
  auditable.
- **A staff profile has one primary department and one primary position.**
  The position may carry a department; when both are supplied they must match,
  and when only the position is supplied its department is copied onto the
  profile. Additional roles and teaching assignments arrive with P3-02.
- **Salary is `salary_santim` and contract data is permission-gated.**
  Contract and salary fields require `staff.contracts.view` /
  `staff.contracts.manage`. A caller with only `staff.view` receives the staff
  record with an empty contract list and `contracts_restricted=true`, while
  the contract endpoints themselves return 403.
- **User accounts are linked, not embedded.** A nullable unique `user_id` on
  the staff profile ties it to an existing account; link and unlink are audited
  actions. Uniqueness is enforced among live staff profiles, so deleting a
  staff record frees the account for a corrected replacement.
- **A repeated person submission is rejected before a new person exists.**
  `create_person` always inserts a person, so staff create first prepares the
  candidate and looks for a live person with the same exact name triplet and
  date of birth (or the same email/phone) that already owns a staff profile.
  That returns `staff.error.person_exists` instead of creating an orphan
  person on every duplicate submission.
- **Departments, positions and qualifications use ordinary row versions.**
  Every mutation takes `row_version` and writes an audit entry through the
  shared `record` helper, matching the rest of the API rather than inventing a
  staff-specific concurrency model.

## 2026-11-18 — P3-02 teaching assignments and data scopes

- **A teaching assignment is one live `(staff, year, section, subject)` row.**
  The composite uniqueness rule is enforced with a partial index over
  `deleted_at IS NULL`, so a soft-deleted assignment can be recreated or
  restored without colliding with itself. The section must belong to the named
  academic year and the subject must be active; both checks run on create,
  update and restore. A terminated staff member cannot receive new assignments.
- **The module manifest declares the scopes a permission accepts.** `staff.view`
  accepts `all` and `department`; `students.view` accepts `all`,
  `assigned_subjects` and `own_class`. The RBAC editor validates grants against
  those declarations, so a school cannot store a scope the module will not
  interpret.
- **Default roles carry the narrow grants.** A plain `teacher` gets
  `students.view` with `assigned_subjects`; a `homeroom_teacher` gets it with
  `own_class`; a `department_head` gets `staff.view` with `department`. These
  are starting points and remain editable like every other default role.
- **`assigned_subjects` and `own_class` resolve to sections for student data.**
  Both scopes narrow *which student rows* a caller can read, using the live
  enrollment section. Student list queries filter by the visible section set;
  direct detail and read subresources (enrollments, guardians, medical,
  documents, photo) return 403 `error.scope_denied` when the student is outside
  the set. An empty set means no rows, never all rows.
- **`department` narrows staff records, not student records.** A department head
  sees only live staff whose primary department is their own. It deliberately
  does not widen access to students: student visibility comes only from the
  explicit `assigned_subjects` and `own_class` scopes.
- **Scope checks run in the service layer as well as the route guard.** The
  route dependency covers the HTTP surface, while the action entry points repeat
  the check so AI or CLI callers cannot bypass visibility by invoking an action
  directly.

## 2026-11-18 — P3-03 leave management

- **Leave durations are stored in integer half-days.** `days_units` is two per
  full day and one per half day, so half-day leave never reaches the database as
  a float and balances always add up exactly. The API still speaks in days
  (`3.0`, `0.5`) and rejects anything that is not a whole or half day.
- **Leave types are a deactivatable catalogue.** A type carries its yearly
  entitlement, whether it is paid, whether it counts against a balance, whether
  approval is required, and sort order. Retiring a type sets `is_active=false`;
  existing balances and historical requests keep pointing at it. A code is
  unique among live types.
- **Balances are one row per staff, academic year and leave type.** The first
  request for a type lazily creates the row with the type's entitlement, so a
  new school can start requesting without pre-seeding every balance. Entitled,
  carried and adjustment values are snapshots; later edits to the type do not
  retroactively rewrite an existing year.
- **Only approved and submitted requests consume balance.** Submitted units are
  shown as pending, approved units as used, and remaining subtracts both. Draft,
  rejected and cancelled requests do not hold balance. Request overlap is
  rejected across draft, submitted and approved rows so the same dates cannot be
  double-booked.
- **The workflow is draft → submitted → approved/rejected, with cancellation.**
  A type that does not require approval moves straight from submitted to
  approved on submission. A type that does not count against a balance can be
  requested without a balance check. Only drafts can be edited, only submitted
  requests can be decided, and cancelled/rejected requests are terminal.
- **Leave shares the staff department scope vocabulary.** `staff.leave.view`
  accepts `all`, `department` and `self`; `staff.leave.request` accepts `all`
  and `self`; `staff.leave.approve` accepts `all` and `department`; managing
  types and balances requires `staff.leave.manage`. A self requester can only
  file or cancel their own leave, and a department approver can only decide for
  staff in their department.
- **The calendar returns requests overlapping a date range.** It defaults to
  draft, submitted and approved rows, because cancelled and rejected requests no
  longer occupy the calendar; an explicit `status` filter overrides that.
- **Requests must stay inside their academic year.** A request whose dates fall
  outside the named year, or that targets a closed year, is rejected. This keeps
  leave balances tied to the year that funded them.

## 2026-11-18 — tiered local verification

- **The full backend suite moves to the phase boundary.** It takes roughly 17
  minutes on the owner's machine, so running it after every task was slowing
  delivery without catching many additional defects: most failures surface in
  the changed module or its direct consumers first.
- **Each task still runs its own tests, the tests of every module it touches,
  and the fast global gates.** Ruff, formatting, i18n, import-linter,
  migration-head checks, route-permission coverage and API compatibility stay
  per-task because they are cheap and catch the highest-cost mistakes (missing
  permissions, broken translations, migration drift, zone violations).
- **Shared-core changes do not get the deferral.** Auth, RBAC, scopes,
  permissions, migrations/models, route ordering/surface, audit/outbox/events
  and widely imported helpers still trigger the full backend suite immediately,
  because a failure there is expensive to debug after several more commits.
- **Phase checkpoints and tags require the full suite.** Tier 1 being green is
  enough to tick a task; tier 2 being green is required to close a phase. This
  keeps the final authority with the complete suite while letting daily work
  stay responsive.
- **UI work runs its own tests, typecheck and build per task, and the full web
  suite plus UI quality gate at the phase boundary.** No test is deleted,
  skipped or weakened by this policy; only the timing of the expensive run
  changes.

## 2026-11-18 — P4-01 pure assessment engine

- **The engine never accepts floats.** `score_percent`, `aggregate`, scores,
  components and year rules take `Decimal`, `int` or numeric strings and raise
  `TypeError` for floats, so binary rounding can never enter a mark. Rounding
  happens only at the boundaries the caller chooses (`converted_score`,
  `component_value`, `term_total`, `year_result`).
- **Non-present statuses are not interchangeable zeros.** `excused`, `exempt`
  and `not_taken` are always excluded. `absent` is excluded by default and
  counts as zero only when the component sets `absent_counts_as_zero`, matching
  ARCH §9.5.2. A component whose scores are all excluded returns `None` rather
  than `0`, so callers can distinguish "nothing to count" from a real zero.
- **Component aggregation matches the ARCH formula.** Percentages are
  aggregated first and the result is multiplied by `max_points`, with one
  rounding at the end. `best_n` keeps the highest included percents, `latest`
  uses input order after excluded scores are removed, `sum_capped` caps the sum
  of percents (default cap 1 = 100%), and `weighted_average` requires a weight
  on every included score.
- **Bonus marks are an assessment-level flag.** `raw > out_of` is rejected
  unless that score sets `allow_bonus`, which then permits a component value
  above its `max_points`. Negative raw scores and non-positive `out_of` values
  are always rejected.
- **Year rules are explicit.** `average`, `sum` and weighted average combine
  term totals; missing (`None`) terms and their weights are skipped, and a year
  with no present terms returns `None`. Precision is limited to 0–6 decimal
  places with all standard Decimal rounding modes.

## 2026-11-18 — P4-02 grade bands and scale assignment

- **Bands carry both edges and are half-open.** Each `Band` has `min_value`
  and `max_value`; resolution uses `[min, max)` and the top band alone includes
  its `max_value`, so 74.99 is below a 75 cutoff while 100 resolves to the top
  band. Validation rejects unsorted bands, duplicate minimums, gaps, overlaps,
  values outside `lower_bound`/`upper_bound`, and bands extending past the top.
- **Display rounding never changes a grade.** `GradeScale.precision` and
  `rounding` are used by `display_value` only. Band resolution always uses the
  exact converted mark, so a 74.99 mark cannot become a C+ merely because the
  report shows one decimal place.
- **Descriptive scales reuse the same thresholds.** A descriptive scale
  (`ScaleType.DESCRIPTIVE`) still maps a numeric mark to a label, but the type
  tells the UI to show the rating rather than a percentage. This keeps mark
  storage identical for KG/lower grades while allowing different band labels.
- **Scale assignment is most-specific-first.** Contexts resolve in the order
  assessment > subject > level > stage > default; an assignment whose key does
  not match or whose scale is not effective on the requested date is skipped.
  Among matches, the latest `effective_from`, then the highest version wins.
  Two different scales at the same date and version raise an ambiguity error
  rather than silently choosing one.
- **Scales are versioned and date-bounded.** `version` is part of the scale
  record and is copied into `GradeResult`, so a published result can remember
  exactly which scale produced its label. `effective_from`/`effective_to` are
  inclusive; `at=None` means "ignore dates" for pure-engine callers.

## 2026-11-18 — P4-03 ranking and promotion rules

- **Tie handling is explicit.** `competition` produces 1, 1, 3, 4, `dense`
  produces 1, 1, 2, 3, and `ordinal` produces 1, 2, 3, 4 with input order
  breaking ties. The ranked output records the value, rank, position and whether
  the student tied, so the UI can show either the rank competition or a simple
  ordered list without recomputing.
- **Promotion compares exact totals; only the displayed average is rounded.**
  A student with a 74.995 average is shown as 75.00 but still fails a 75
  minimum. Per-subject minima override `pass_mark` for that subject, and every
  subject below its effective minimum counts against `max_failed_subjects`.
- **The P2-11 hook is the integration point.** `promotion_rule_resolver(policy,
  results_by_student)` lives in `modules/students/progression_rules.py` and
  returns a `RuleResolver`; P4-08 will build the results map from published term
  results. A student without results keeps the level-based default, a pass at
  the final level maps to `graduate`, and a fail maps to `repeat`. This keeps
  assessment free of student tables and the promotion service free of
  assessment tables.

## 2026-11-18 — P3-04 staff UI and mobile directory

- **The web staff page is one module with catalog tabs.** Directory, departments,
  positions, leave types and the leave calendar live behind `/staff`, so the
  module navigation item from the manifest is the only entry point. The
  directory tab is the default; catalog tabs are only shown to users with the
  related read permission.
- **Permission gates mirror the API, not a second role model.** `staff.view`
  opens the module, `staff.manage` reveals create/edit controls,
  `staff.contracts.view` decides whether the contracts tab exists at all, and
  the leave controls use the separate view/request/approve/manage permissions.
  A hidden control is never the only defence: every mutation still calls its
  permission-protected endpoint.
- **Leave stays explicit.** Creating a leave request saves a draft; the user
  then submits it, and a manager approves or rejects it with an optional
  decision note. This matches the backend workflow and keeps the audit trail
  honest, rather than silently auto-submitting from the form. The calendar
  reads the API's overlap window and filters statuses client-side for the
  current view.
- **Money input never passes through a float.** Contract salaries are entered as
  ETB text, converted with `parseMoney`, and displayed with `formatSantim`, so
  the santim value remains an integer end to end.
- **Soft deletes are the only delete actions exposed.** Contract, qualification
  and document removal call the audited soft-delete endpoints; the UI does not
  offer a hard delete. Restoring those records remains an API/audit operation in
  this phase.
- **Mobile stays a read-only directory.** Staff list, search, status filter and
  a basic profile (employment, contact and notes) are available offline-cached
  through the same session/token helpers as the student directory. No staff
  editing or leave workflow is exposed on mobile yet; those remain web-only
  until a later mobile task.

## 2026-11-18 — P3-05 optional payroll sub-module

- **Payroll is an installable module, not part of `staff`.** It has its own
  manifest (`payroll`, `depends_on=["staff"]`, `default_enabled=False`) and its
  own `payroll.view`/`payroll.manage`/`payroll.run` permissions. A school that
  does not run payroll never sees the tables enabled, and the module gate
  returns `MODULE_DISABLED` exactly like every other optional module.
- **No tax or pension rates are shipped.** The engine, tables and API are
  complete, but starter rules would look authoritative and could pay people
  incorrectly. The accountant creates a draft rule set, enters the validated
  rates, activates it, and only then can a run exist. Rule sets expose an
  `accountant_notice` message key and a `verified_by_accountant` flag; the
  notice is worded as "configuration, not law".
- **Money and rates are integers end to end.** Payslip amounts are santim
  (`BigInteger`), rates are basis points (`0…10000`), and the pure engine uses
  `divmod` with an explicit rounding mode. No float ever touches pay. Each
  bracket slice and each percentage is rounded before it is added, so a stored
  payslip line can be recomputed exactly from its `base_santim` and
  `rate_basis_points`.
- **Brackets must be contiguous from zero.** A progressive rule either continues
  upwards (open-ended last bracket) or stops early to express a contribution
  cap. Gaps, overlaps, a non-zero first lower bound, a negative bound, or an
  open-ended bracket that is not last are rejected at input time and again at
  activation.
- **Rule sets are versioned and frozen.** Rules can only be edited while the set
  is a draft. Activation archives the previously active set in the same audited
  transaction; a later rate change means a new version, so a finalized payslip
  always points at the exact set that produced it. An active set cannot be
  deleted, and a set used by a run cannot be deleted at all.
- **Basic salary is always taxable and pensionable.** Allowances carry their own
  `is_taxable`/`is_pensionable` flags; employer-paid rules are recorded on the
  payslip but never add to gross or reduce net. Deductions that exceed gross
  reject the whole calculation rather than paying a negative amount.
- **A run is a month with a snapshotted result.** Creating a run needs an active
  rule set and a unique live `(year, month)`. Calculation replaces previous
  payslips for that run (soft-deleting them first so the live-unique
  `(run_id, staff_id)` index never conflicts) and skips staff with no active
  contract/salary. Finalizing is one-way: recalculation and deletion then
  return 409, preserving the payroll history the accountant reviewed.
- **Payslip PDF is deliberately out of scope.** This task builds the data model,
  engine and API only. Document Studio will render the PDF from a finalized
  payslip's stored lines, so pay history does not depend on a template that can
  change later.
- **Payroll permissions are seeded onto the accountant and HR roles.** The
  accountant gets view/manage/run; the HR officer gets view/manage for salary
  components but not the run permission, keeping the payroll-approval step with
  finance. Existing instances keep local edits because default roles are only
  created when missing; a reset restores the shipped matrix.

- **Attendance has one school-wide mode.** Module settings hold `mode`
  (`daily` or `per_period`), `require_reason` and `allow_future_dates`, so a
  school does not mix register shapes across sections. Per-period registers
  carry their own `period` number because the timetable module (P6-07) does not
  exist yet; when it lands, the period becomes a validated timetable slot
  without changing the register or record tables.
- **Opening a register seeds the roster as present.** Session creation writes
  one `present` record per actively enrolled student in one transaction, which
  makes the common "everyone is here" case a single tap and keeps the register
  complete for reporting. Bulk entry (`PUT`-style upsert) is idempotent by the
  natural key `(session_id, student_id)`: an omitted reason, note or late count
  clears the old value, while the single-record `PATCH` only changes supplied
  fields. Both accept an optional `row_version` so offline clients can detect a
  stale write.
- **Registers follow `open → submitted → locked`, and only `open` accepts
  entry.** `attendance.record` may submit; `attendance.manage` locks and may
  reopen a locked register. Records and sessions are soft-deleted, never
  hard-deleted, and every transition is audited through the service layer.
- **Attendance entry works offline on mobile through a coalescing outbox.** A
  network failure during entry stores the changes in the school's secure
  storage keyed by `(session, student)`, replacing an earlier draft for the same
  student so a long offline session still replays one row per student. The
  outbox is flushed in one bulk call per register when the device reconnects;
  because the API upserts on the natural key, replaying the same payload cannot
  create duplicates. A failed flush keeps the entries on the device for the next
  attempt instead of discarding a teacher's work.
- **The web register shows the roster, not a raw record list.** Opening a
  session seeds every enrolled student as present, so the grid renders the
  roster and lets the teacher change only exceptions. Saves send just changed
  students in chunks of at most 200, keeping large sections within the bulk API
  limit while the response refreshes the whole register.

## 2026-11-18 — P3-08 staff attendance, absence events and reports

- **Staff attendance lives in `staff`, not `attendance`.** Student registers are
  per session and per section; staff presence is one row per `(staff, date)`.
  Keeping it in `staff` lets the existing staff scopes (`all`, `department`,
  `self`) apply unchanged and avoids a second meaning of "session". The table is
  `staff_attendance`, and the live unique index on `(staff_id, date)` makes an
  offline replay or correction idempotent.
- **Only employed staff appear on the day roster.** `active` and `on_leave`
  staff are listed; suspended, resigned and terminated staff are excluded and
  cannot be recorded, because their contract no longer funds attendance.
  `leave` is a status on the day row, not a copy of an approved leave request.
- **Recording is a bulk upsert with an optional row version.** The day view
  returns the roster with `record_id` and `row_version`, so the UI sends only
  exceptions. An omitted reason or note clears the old value on upsert (the row
  is the full status), while a stale `row_version` returns 409. Create and
  update are separate audit actions: nothing is written for an unchanged
  replay.
- **`attendance.absent_marked` fires only on a transition to absent.** A newly
  created absent record emits it, and an update emits it only when the previous
  status was not already absent. Replaying the same absent entry, or correcting
  another field on an already-absent row, emits nothing. The payload carries
  session/record/student/year/section/date/mode/period/reason/late count and
  is written in the same transaction as the record, so automation cannot see an
  absence that was rolled back.
- **Reports are integer aggregates, not rows fetched and summed in Python.**
  Student rows group by `(student, year, section)` and section rows by
  `(year, section)`, which keeps a promoted student's history in the right
  section. Percentages are integers: `attended = present + late` and
  `rate_percent = round_half_up(attended * 100 / total)`. The threshold
  comparison uses that integer, so the same data cannot cross the threshold
  differently on two platforms. `below_only` filters after aggregation, and
  `limit` caps the response after sorting.
- **Reports are scoped before aggregation.** `visible_section_ids` is applied to
  the session join, so a caller with `assigned_subjects` or `own_class` scope
  cannot infer another section's rate from a threshold sweep. An explicit
  `section_id` outside scope yields an empty report rather than a 403, which
  keeps list views simple without leaking existence.
- **A report range is closed and bounded at 366 days.** The check runs in the
  service as well as the schema so an action caller gets the same keyed error as
  an HTTP caller (`attendance.error.report_range`/`_too_long`). Staff summaries
  use the same reversal check (`staff.error.attendance_range`).

## 2026-11-18 — P3-SEED demo staff, teaching, attendance and leave

- **A staff profile can be created from an existing person.** `POST /staff`
  now accepts either `person` (register a new person) or `person_id` (hire a
  person the school already knows, such as a guardian), and rejects both or
  neither. The demo seed uses `person_id` so the people created by P2-SEED are
  reused instead of duplicated, and the API gains the same path a real school
  needs when a parent joins the staff.
- **The demo school now licenses the attendance module.** The seed's module list
  includes `attendance`, so a freshly seeded instance can open registers and
  reports without a manual toggle. Payroll stays opt-in and off.
- **Seeded staff are placed in two departments with two positions.** Teachers go
  to `teaching`/`teacher`, office staff to `administration`/`administrator`.
  This gives department-scoped leave and attendance a real target in the demo
  without inventing a full org chart.
- **Teaching assignments cover one homeroom per teacher.** teacher1 gets
  mathematics, science and ICT in Grade 5 A; teacher2 gets English, Amharic and
  social studies in Grade 6 A. The owner script can log in as either teacher and
  observe `assigned_subjects` isolation on attendance and marks.
- **A deterministic school week is recorded for every demo staff member.** The
  week of 14–18 September 2026 stays `present` except one late arrival (HR), one
  sick absence and one approved leave (teacher2), so the roster, summary and
  report screens have interesting data on first boot.
- **Two leave types and two requests complete the workflow.** Annual (20 days)
  and sick (10 days) leave are created if missing; teacher1's two-day annual
  request is submitted and approved, teacher2's one-day sick request stays
  submitted. Requests are matched on staff, dates and reason before creation, so
  a re-run neither duplicates them nor adds audit rows.

## 2026-11-18 — P4-04 assessment models and migration

- **Marks are stored as signed integer micro-units in `BIGINT`.** Every mark
  column uses the `Mark` type decorator (six decimal places, the engine's
  `MAX_PRECISION`), so `0.1 + 0.2` cannot become `0.30000000000000004` in a
  database that lacks a native exact decimal. Services and the pure engine keep
  working with `Decimal`; only the type decorator knows about micro-units. A
  migration assertion checks that `assessment_assessments.out_of` is `BIGINT`,
  which fails loudly if anyone changes it to a float column.
- **Raw values are copied onto the score.** `Score.out_of` is a snapshot of the
  assessment's maximum at entry time, and `Score.converted` is a stored derived
  value. A later edit to an assessment (or to a structure) therefore cannot
  silently reinterpret a historical raw score; recalculation rewrites only
  `converted`.
- **Live unique indexes are partial indexes keyed by a deterministic scope
  string.** SQLite and PostgreSQL both treat `NULL`s as distinct, so a nullable
  `level_id`/`stage_id`/`subject_id` cannot prevent duplicate school-wide rows.
  `scope_key` (`school`, `level:<id>`, …) is stored next to the FK and covered
  by a unique index filtered on `deleted_at IS NULL`. The same pattern protects
  component keys, one live default grade scale, scale assignments and
  submissions.
- **Every score change has an append-only revision row.** The audit log records
  who did what; `assessment_score_revisions` keeps the old and new raw and
  converted values together so a report-card reprint can explain a change
  without parsing audit payloads; `assessment_result_snapshots` stores the
  version of the structure and scale used to publish a result.

## 2026-11-18 — P4-05 structure management, impact preview and recalculation

- **Marks cross the HTTP API as decimal strings.** `Mark` inputs accept an
  integer or a numeric string and are parsed into `Decimal`; every mark output
  is a string with trailing zeros removed (`10.000000` becomes `"10"`). JSON
  numbers are never used for marks, because one float round-trip is enough to
  break an exact grade boundary. The P4-01 engine still rejects Python floats
  outright.
- **An edit never touches raw scores.** When a component maximum, an
  aggregation setting or the rounding changes, the API writes an
  `assessment.structure.update` audit entry, creates an
  `assessment.recalculate` job and returns its id. The job recomputes
  `Score.converted` from the untouched raw values and writes one
  `assessment.structure.recalculate` entry with counts. The API attaches the job
  row in the same transaction; the broker enqueue happens after commit and is
  skipped in test runs (the same pattern as thumbnails), so tests exercise the
  worker code directly without Redis.
- **The impact preview is the same calculation as the job.** `POST
  /structures/{id}/impact` accepts the proposed components and reports the
  number of assessments, scores, students and changed values plus up to five
  before/after samples. It is a dry run: nothing is written. The editor uses it
  before saving so a maximum change is never a surprise.
- **The component total is a warning, not a hard cap, unless it exceeds the
  intended total.** The editor shows "components add up to X, not the intended
  Y" and still saves. A total *greater* than the intended total is rejected
  (`assessment.error.component_sum`) because that would make every result
  exceed 100% without an explicit decision. Inactive components stay in the
  structure but are excluded from conversion by the engine.
- **A component with marks cannot be removed, and a component key is
  immutable.** Removing a component with assessments would orphan scores or
  silently drop them from result totals, so it returns `409
  assessment.error.component_in_use`. Renaming a key would break stored
  `component_id` references and external reports; a new component can be added
  instead. A structure that already has marks cannot be deleted either.

## 2026-11-18 — P4-06 assessment and score APIs

- **The most specific mark structure wins automatically.** Creating an
  assessment resolves a structure for the section's level and the subject:
  subject > level > school. A stage-scoped structure is only used when the
  caller names `structure_id`, because a section carries a level but the
  academics model has no level→stage link yet. This keeps the default path
  predictable while leaving stage-scoped configuration usable.
- **`out_of` is copied onto scores and becomes immutable once a mark exists.**
  The assessment maximum at entry time is the denominator a raw score was
  entered against. Allowing it to change later would silently reinterpret
  history, so `PATCH` returns `409 assessment.error.out_of_locked` as soon as
  one score row exists; the assessment can be deleted and recreated while it is
  still empty. `allow_bonus` may still be turned off, but only when no existing
  raw value exceeds the maximum.
- **Scores upsert on the natural key `(assessment, student)`.** Repeating a
  request is a no-op: unchanged rows are counted, not rewritten, and no revision
  or audit row is produced. This is what makes the web grid's autosave and a
  mobile offline retry safe without relying on an `Idempotency-Key` (the HTTP
  middleware still honours one when the client sends it). An optional per-entry
  `row_version` adds optimistic concurrency for a grid that read a row, and a
  stale value returns `409` with the current score state.
- **Every applied score change writes a revision and an audit entry.** The
  revision stores the old/new raw, status and converted values plus the reason
  of the request, so a report-card explanation does not depend on parsing audit
  JSON. The audit entry is written through the service, keeping the "every
  mutation audited" rule even for bulk entry.
- **Scope is resolved to (section, subject) pairs.** `assigned_subjects` maps to
  the teacher's `StaffTeachingAssignment` pairs, `own_class` to every subject in
  the homeroom section, and `department` to the pairs taught by staff in the
  caller's department (so a department head can review their teachers' marks).
  List endpoints translate the same access into a SQL condition; point reads
  and writes assert it and return `403 error.scope_denied`.
- **A teacher can only create an assessment for a pair they teach.** The router
  requires `assessment.enter_marks`, and the service narrows it to the assigned
  pair before resolving the structure, so a crafted `section_id` cannot reach
  another class.

## 2026-11-18 — P4-07 mark workflow and corrections

- **The submission state machine is explicit and forward-only.** The only
  transitions are `draft → submitted → approved → published → locked`, plus a
  rejection that returns `submitted → draft`. Any other change (for example
  publishing a draft, approving twice or resubmitting) returns `409
  assessment.error.submission_state` with the current and allowed states, rather
  than silently coercing the row. A `row_version` on the action gives optimistic
  concurrency when the client read a stale card on screen.
- **Score entry stops at submission and resumes on rejection.** The service
  checks the live submission before every score upsert and returns `409
  assessment.error.marks_not_draft` once the marks moved past `draft`. Approving
  a correction is the single deliberate exception: it writes the corrected
  score directly because the correction is the authorised post-lock path.
- **Marking windows are optional deadlines, not required configuration.** If no
  active window exists for the term and scope, entry stays open. Once at least
  one active window exists, entry and submit require one of them to be currently
  open, otherwise `422 assessment.error.window_closed`. Windows can apply to the
  whole school, a level or one section; a more specific window does not override
  an open broader one, so a section can be reopened without clearing the term's
  main window.
- **A submission cannot be submitted without at least one raw mark.** The count
  deliberately ignores absent/excused-only sheets: a teacher must have entered
  at least one real value, otherwise the review queue would fill with empty
  subjects (`422 assessment.error.no_marks`). Rejection keeps the teacher's note
  and clears `submitted_at`/`submitted_by`, so the draft looks untouched while
  the audit trail still records the return.
- **Corrections exist only after lock.** Requesting one for a draft, submitted,
  approved or published submission returns `409
  assessment.error.not_locked`. Only one pending request is allowed per score
  (`409 assessment.error.correction_pending`), and a request whose proposed value
  equals the current mark is refused (`422
  assessment.error.correction_unchanged`) so the queue stays meaningful.
- **Accepting a correction rewrites the score through the normal validation
  path.** It validates the proposed mark against the assessment and component,
  recomputes `converted` with the stored structure rules, bumps the score's
  `row_version`, and appends a `ScoreRevision` with `source="correction"` and
  the request id. The old raw value remains in the revision and audit entry;
  nothing is hard-deleted or overwritten without a trace. Rejecting records the
  decision and leaves the score untouched.
- **Correction and submission scopes reuse the mark scope.** Requesting a
  correction requires `assessment.correct` (`assigned_subjects`), deciding it
  requires `assessment.correct_approve` (`department`), and both point reads
  and writes assert the same section/subject pair as score entry. A teacher
  outside the pair gets `403 error.scope_denied` rather than a silent empty
  result.

## 2026-11-18 — Phase 16 website module spec linked

- **The public school website is a separate licensable module built as Phase 16.**
  `docs/03_WEBSITE_MODULE.md` (WEB) is the third specification document. The
  module has its own tables, permissions and i18n namespace, is default-off and
  licensable, and talks to the rest of the ERP only through actions, events and
  whitelisted service functions. It is built only after the Phase 15 RELEASE
  CHECKPOINT; nothing in Phase 0–15 changes because of this decision.
- **The ERP web app moves under `/app` only in task P16-02.** `APP_BASE_PATH`
  defaults to `/app` in production and `/` in local development. No route, link,
  Vite base or e2e test changes before P16-02; that task runs the full suite and
  the smoke e2e and fixes every break before the phase continues.
- **Announcements get no public flag.** The communication module stays unaware
  of the public site. A "publish to website" action in the website module reads
  an announcement and creates a **draft** news post that a human reviews and
  publishes, so a private or internal announcement can never leak automatically.
