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
