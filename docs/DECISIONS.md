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
