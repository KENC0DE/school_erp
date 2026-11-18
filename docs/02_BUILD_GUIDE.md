# School ERP Platform: Build Guide for the Builder AI

**Document 2 of 2.** Follow this checklist in order. The design lives in `01_PROJECT_ARCHITECTURE.md` (called **ARCH** below). Section references like `ARCH §9.5` point there.

---

## 0. How to work (read this first, every session)

### 0.1 Session start routine
1. Open `docs/PROGRESS.md` and find the first unchecked task.
2. Read only the ARCH sections that task cites. Do **not** load the whole repository or whole documents into context.
3. Do the task. Run its **Verify** step. Tick it in `PROGRESS.md`. Commit. Continue.

### 0.2 Non-negotiable rules
1. **One task at a time, in order.** Never start the next task while the current one fails verification.
2. **Walking skeleton first (Phase 0).** Thin code, every connection real. Muscles are added phase by phase afterwards.
3. **Tests with every task.** Logic tasks: write the tests first. Never delete, skip or weaken a test to get green.
4. **Checkpoints are gates.** At the end of each phase, run the CHECKPOINT list. All items must pass before the next phase starts.
5. **No hard-coded user-facing text** (use i18n keys), **no hard-coded colors** (use tokens), **no floats for money or marks**, **no hard deletes**, **no unaudited mutations**, **no endpoint without a declared permission**.
6. **All mutations go through service functions**, and shareable operations are registered **Actions** (ARCH §6).
7. **Everything optional is a module** with a manifest (ARCH §4.5). Nothing outside `core/` may import another module's tables.
8. **External services sit behind adapters** and are stubbed until credentials exist (payments, SMS, AI providers). Never block on missing credentials.
9. **Verify library APIs against current official documentation** before using them. Pin exact versions. Do not trust memory for fast-moving libraries (Tailwind, Expo, shadcn/ui, Celery, OR-Tools, Playwright, i18next).
10. **Ambiguity:** choose the simplest option consistent with ARCH, record it in `docs/DECISIONS.md` (date, decision, reason), and continue. If truly blocked, write to `docs/QUESTIONS.md` and work on another task.
11. **Keep files small** (aim under ~400 lines) and functions focused. Prefer clear names over comments.
12. **Commit per task** with the message `P{phase}-{nn}: short description`. Never commit secrets. Keep `.env.example` current.
13. **Seed data and the dev launcher are updated at the end of every phase** (task `Pn-SEED`), so the owner can test what exists.
14. **Respect the zone boundaries** (ARCH §4.4): `school-erp/` never imports `owner/`; `owner/` uses only `shared/` and the school HTTP API; `shared/` imports neither. The boundary check in CI must always pass.
15. **Keep the school API backward compatible** within `/api/v1` (additive only, ARCH §8.10), because one mobile app talks to schools running different versions.
16. **Follow the UI standards** (ARCH §11.5). Build screens only from the shared UI kit and tokens. Every screen needs loading, empty and error states, and must pass the UI quality gate in 0.3 before its task is ticked.
17. **Work autonomously until the project is complete** (section 0.7). Do not stop to ask whether to continue, do not pause between tasks or phases, and do not wait for approval. Only the narrow stop conditions in 0.7 apply.

### 0.3 Definition of Done (every task)
- [ ] Code implemented and matches ARCH.
- [ ] Tests added and passing. Lint and type check clean.
- [ ] Permissions, audit and i18n handled where relevant.
- [ ] **Screens only (UI quality gate):** loading, empty and error states present; screenshots at desktop (1440), tablet (768) and phone (390) widths in light and dark mode and in `en` and `am`; automated accessibility check with no serious violations; `docs/UI_CHECKLIST.md` passed; only shared components and tokens used.
- [ ] `docs/PROGRESS.md` updated. Commit made.

### 0.4 Standard commands (create in P0-25, keep working forever)
```
./scripts/dev.sh up        # start everything for local testing
./scripts/dev.sh seed      # (re)load demo data and demo accounts
./scripts/dev.sh reset     # wipe local data, rebuild, reseed
./scripts/dev.sh test      # run all automated tests
./scripts/dev.sh mobile    # start Expo for Expo Go on a phone (points the app at your computer's LAN address)
./scripts/dev.sh logs|down
```
Windows: `scripts/dev.ps1` with the same subcommands.

### 0.5 Local ports (dev)
API 8000 · Controller API 8100 · School web 5173 · Controller web 5174 · Postgres 5432 · Redis 6379 · MinIO 9000/9001 · Mailpit 8025 · Expo 8081.

### 0.6 Repository zones (see ARCH §4.4)
`school-erp/` (backend + web, deployed per school) · `owner/` (controller-api, controller-web, and the **single mobile app for all schools**) · `shared/` (py + ts contracts and utilities) · plus `deploy/`, `scripts/`, `docs/`.


### 0.7 Autonomous operation (the builder never waits for the owner)

**Mission:** keep building, in guide order, until the **FINAL CHECKPOINT** at the end of Phase 15 is complete. Finishing a task or a phase is never a reason to stop.

**The loop (repeat without pausing)**
1. Read `docs/PROGRESS.md`, take the first unchecked, non-blocked task.
2. Implement, test, verify, tick it, write a one-line note in `PROGRESS.md`, commit.
3. Immediately start the next task. **Never end a turn with "should I continue?", a summary that waits for a reply, or a request for permission.**
4. At the end of a phase, run its CHECKPOINT. If it passes, tag it and start the next phase at once. If it fails, fix the cause and re-run. Never skip a checkpoint and never weaken a test.

**Owner-review items never block you.** Wherever this guide says the owner reviews, approves or tests something (for example the design foundation, the owner test scripts, printed PDFs), do this instead of waiting: do your own review against `docs/UI_CHECKLIST.md` and the phase checkpoint, save screenshots or sample outputs under `docs/review/<phase>/`, add an entry to `docs/OWNER_REVIEW.md` (what to look at, how to run it, what good looks like), and continue. The owner will review later and file any changes as new tasks.

**When a task fails or is unclear**
1. Find the root cause. Try up to **three genuinely different approaches**.
2. Still stuck: record what you tried in `docs/QUESTIONS.md`, mark the task `[~]` (blocked) in `PROGRESS.md`, and move to the next independent task.
3. Revisit every `[~]` task at the end of its phase and again before the final checkpoint, with fresh eyes.
4. Ambiguous requirement: choose the simplest option consistent with ARCH, record it in `docs/DECISIONS.md`, and continue.

**Things you cannot do yourself: stub and continue.** Real payment-provider credentials, SMS provider accounts, AI provider keys, Apple/Google developer accounts, a physical phone, and real production servers are not available to you. Build everything behind adapters with test doubles and fakes (as the tasks already say), document exactly what the owner must supply in `docs/OWNER_ACTIONS.md`, and move on.

**The only legitimate reasons to stop**
- The final checkpoint is complete and `docs/FINAL_REPORT.md` is written.
- Every remaining task is blocked (`[~]`) after the revisit passes.
- The next action would be **irreversible or leave the repository**: deleting data outside the repo, force-pushing or rewriting published history, publishing to an app store or registry, spending money, sending real emails/SMS/push to real people, or using real credentials. Do not do these. Record them in `docs/OWNER_ACTIONS.md` and continue with other work.

**Guardrails that make autonomy safe**
- Work on a branch per phase (`phase-N`), merge into `main` only when its checkpoint is green, and tag each phase.
- Commit after every task so any step can be undone. Never rewrite history.
- Never touch files outside the repository. Never run commands that need `sudo`. Never add real secrets to the repo.
- Quality is not traded for speed: no deleted, skipped or weakened tests; no silenced boundary or lint checks.
- Optional work is skipped unless requested: Phase 13 add-ons are built only if listed in `docs/OWNER_REQUESTS.md`, and P15-07 (repo split) is documented but never executed.

**Memory across sessions:** your context is limited. `PROGRESS.md` (state), `DECISIONS.md` (choices), `QUESTIONS.md` (blockers), `OWNER_REVIEW.md` and `OWNER_ACTIONS.md` are your memory. Update them as you go, and start every session by reading them.

**If you work with sub-agents or in parallel:** the same autonomy and guardrail rules apply to each of them. One integrator is responsible for running checkpoints and for keeping the loop going.

**At the very end:** write `docs/FINAL_REPORT.md` with what was built, what was verified (and how), the `[~]` tasks left, everything in `OWNER_REVIEW.md` and `OWNER_ACTIONS.md`, and how to run `./scripts/dev.sh up` and `seed`.

---

## 1. Demo accounts for testing (dev only)

Created by `./scripts/dev.sh seed`. **The seed script must refuse to run when `APP_ENV=production`.** All demo accounts use the dev password `DevPass#2026`. Never use these anywhere real.

**Mobile app:** on the school picker enter the school code `DEMO` (a second demo school, `DEMO2`, appears from Phase 11), then log in with any school account below.

**Controller (http://localhost:5174)**

| Account | Role | Purpose |
|---|---|---|
| `owner@controller.local` | Platform Owner | Full CP access, open schools as admin |
| `support@controller.local` | Controller Support | Limited CP role |

**Demo school "Demo Academy" (http://localhost:5173)**

| Account | Role | Test it for |
|---|---|---|
| `superadmin@demo.school` | School Super Admin | Roles, modules, settings, activity history |
| `director@demo.school` | Director | Approvals, dashboards |
| `academichead@demo.school` | Academic Head | Mark structure, grade rules, approving marks |
| `registrar@demo.school` | Registrar | Admissions, student records, documents |
| `teacher1@demo.school` | Teacher (Math, Grade 5) | Mark entry, attendance |
| `teacher2@demo.school` | Teacher (English, Grade 6) | Scope limits (cannot see Grade 5 data) |
| `accountant@demo.school` | Accountant | Fees, payments, receipts |
| `hr@demo.school` | HR Officer | Staff, leave |
| `limited@demo.school` | Custom role with few permissions | Hidden menus and permission denial |
| `parent1@demo.school` | Parent (2 children) | Portal |
| `student1@demo.school` | Student | Portal |

Seed data grows each phase: a few classes, ~60 students with Ethiopian three-part names in Amharic and Latin, staff, one academic year in semester mode, sample marks, sample invoices, sample templates.

---

## PHASE 0: Walking skeleton

**Goal:** one thin, working path through every part of the system so all connections are proven: controller ↔ instance, backend ↔ web, mobile, controller web, worker, storage, i18n, themes, modules, permissions, audit, AI wiring and PDF with Amharic text. Keep each piece minimal. Do not build real features yet.

**Cites:** ARCH §4, §5, §6, §8.

### Repository and infrastructure
- [ ] **P0-01** Create the single repo with its three zones per ARCH §4.4 (`school-erp/`, `owner/`, `shared/`; pnpm workspaces + `uv` workspace). Add `.gitignore`, `.editorconfig`, pre-commit (ruff, prettier, eslint), `.env.example`, LICENSE placeholder. **Verify:** `pnpm install` and `uv sync` succeed.
- [ ] **P0-01b** **Enforce the zone boundaries** (ARCH §4.4): Python `import-linter` contracts and TypeScript restricted-import rules (ESLint or dependency-cruiser), wired into CI and pre-commit. **Verify:** deliberately violating fixtures (`school-erp` importing `owner`, `owner` importing `school-erp` code, `shared` importing either) make the check fail.
- [ ] **P0-02** Create `docs/PROGRESS.md` (copy of all task IDs from this guide as a checklist), `docs/DECISIONS.md`, `docs/QUESTIONS.md`, and copy both specification documents into `docs/`.
- [ ] **P0-03** `deploy/compose/dev.yml`: Postgres (two databases: `erp_demo`, `controller`), Redis, MinIO, Mailpit. **Verify:** all containers healthy.

### Backend skeleton (school instance)
- [ ] **P0-04** FastAPI app factory, `pydantic-settings`, `/health` and `/ready`, structured logging, request-id middleware, standard error format (ARCH §5.1). **Verify:** pytest hits `/health`.
- [ ] **P0-04b** Version info (ARCH §8.10): public `GET /api/v1/system/info` returning `api_version`, `app_version`, `min_client_version`; authenticated `GET /api/v1/system/capabilities` listing features derived from enabled modules. **Verify:** tests for both, and that disabling a module changes capabilities.
- [ ] **P0-05** Async SQLAlchemy + Alembic (`core` branch), base model mixins (id, timestamps, soft delete, `row_version`, created/updated by). **Verify:** migration applies to empty DB.
- [ ] **P0-06** **Module registry:** `ModuleManifest`, loader scanning `modules/*/manifest.py`, dependency validation, router mounting, `GET /api/v1/system/modules`. Add a throwaway `sample` module. **Verify:** test lists `sample`; a cyclic-dependency fixture is rejected.
- [ ] **P0-07** Auth skeleton: `users`, Argon2id, login, short-lived access + refresh token rotation, `GET /me`. **Verify:** login test, bad-password test.
- [ ] **P0-08** RBAC skeleton: permissions collected from manifests, `roles`, `role_permissions`, `user_roles`, `require()` dependency, `GET /me/navigation`. **Verify:** allowed/denied tests, plus a test that fails if any route lacks a permission declaration.
- [ ] **P0-09** **Three-gate module gating:** `instance_modules`, `license_state`, `403 MODULE_DISABLED`. **Verify:** disabling `sample` hides it from navigation and blocks its API instantly.
- [ ] **P0-10** **Audit skeleton:** `audit_log` with hash chain, `audit_outbox`, audit service used by one sample mutation, DB migration that revokes UPDATE/DELETE for the app role, `verify_chain`. **Verify:** tamper test detects a changed row.
- [ ] **P0-11** Events and jobs: outbox-based event bus, Celery worker + beat, one ping task, `jobs` table. **Verify:** worker processes a task and updates a job row.
- [ ] **P0-12** **Action registry skeleton:** `@action` decorator, registry, `GET /api/v1/ai/tools` filtered by the user's permissions and enabled modules. **Verify:** two users see different tool lists.
- [ ] **P0-13** i18n skeleton: `translation_entries`, layer merge (default < central < school), `GET /api/v1/i18n/{locale}/{ns}` with ETag, seed `en` and `am` sample strings. **Verify:** a school-layer override beats the default.
- [ ] **P0-14** Themes skeleton: `shared/ts/tokens` (token schema, default Light and Dark, validator), `GET /api/v1/themes/active`. **Verify:** validator rejects a theme missing the dark variant.

### Control plane skeleton
- [ ] **P0-15** `owner/controller-api`: FastAPI app with its own DB, owner login, `schools` table, Ed25519 signing keypair, `POST /enroll`, signed license issuing (EdDSA JWT), `POST /heartbeat`, `POST /audit/ingest`. **Verify:** unit tests for license sign/verify (`shared/py`), including expiry and a tampered token.
- [ ] **P0-16** **Instance ↔ controller link:** instance enrolls with a one-time token, stores the license, verifies it offline, applies the module list, runs a heartbeat task, ships `audit_outbox` batches to the controller. **Verify:** integration test with both apps: toggle a module in the controller, see it change in the instance after a heartbeat; an audit entry created in the instance appears in the controller vault with a valid chain.
- [ ] **P0-16b** **School directory skeleton** (ARCH §8.9): unique, non-guessable `school_code` per school; controller `GET /directory/resolve?code=` returns a **signed** record `{instance_id, name, api_base_url, logo_url, status, min_app_version, kid, signature}`; rate-limited; unknown codes get a generic error; QR payload `erpapp://school/<code>`. Seed school code `DEMO` for the local demo instance. **Verify:** unit tests for signing and verification, key rotation by `kid`, rate limiting, and `suspended` status being returned.
- [ ] **P0-17** **Controller session skeleton** (ARCH §8.6): controller issues a short-lived signed support token with a reason; instance accepts it at `POST /auth/controller-session`, creating an actor `controller` with the Super Admin permission set. **Verify:** actions in such a session are audited with `via=controller`; an expired or tampered token is rejected.

### Frontends
- [ ] **P0-18** Shared packages: `api-client` generated from OpenAPI (script `pnpm gen:api`), `tokens` → CSS variables and RN theme object, `i18n` runtime loader (loads from the API with caching), `module-sdk` (frontend manifest types and registry), stubs for `calendar` and `money`. **Verify:** generation script runs in CI and fails on a diff.
- [ ] **P0-19** **`school-erp/web`:** Vite + React + TS + Tailwind v4 + shadcn/ui init, router, login, authenticated shell with sidebar from `/me/navigation`, theme provider from tokens (light/dark switch), i18n loaded from the API with `en`/`am` switch, a dashboard showing one translated string, and the `sample` module page. **Verify:** Vitest render test; manual check that disabling `sample` removes its menu item.
- [ ] **P0-19b** **Web design foundation** (ARCH §11.5), done before any feature screens: tokens for spacing (8-point scale), type scale, radius and shadows in `shared/ts/tokens`; bundled fonts (clean Latin sans + Noto Sans Ethiopic) with tabular numerals; the shared UI kit in `shared/ts/ui-web` (buttons, inputs, select, date picker with EC/GC, dialog, side sheet, toast, badge, tabs, skeleton, empty state, error state, page header, data table, form layout, sidebar/top-bar shell, controller-session banner); three reference screens (a list with filters, a form, a dashboard) using only the kit; `docs/UI_CHECKLIST.md` distilled from ARCH §11.5; lint rules banning hard-coded colors, font sizes and spacing outside tokens. **Verify:** the three screens render cleanly in light and dark, in `en` and `am`, at 1440, 768 and 390 widths; you review it against `docs/UI_CHECKLIST.md`, save the screenshots under `docs/review/p0/` and log it in `docs/OWNER_REVIEW.md` (the owner reviews later and does not block progress).
- [ ] **P0-20** **`owner/controller-web`:** login, schools list, school detail with module toggles, "Open as school admin" (asks for a reason), a basic vault audit list. **Verify:** component tests plus the e2e in P0-26.
- [ ] **P0-21** **`owner/mobile`, the ONE app for all schools:** Expo app with Expo Router. The first screen is the **school picker**: enter a school code or scan a QR code, call the controller's `GET /directory/resolve`, **verify the signed response** against the embedded controller public key, store the school profile (id, name, api_base_url, logo, versions), then log in against **that school's server** with tokens in `expo-secure-store` **namespaced per school**. After login: a shell with the same navigation as web, an `en`/`am` switch, the school's theme from tokens, running in Expo Go. **Verify:** Jest tests: a tampered directory response is rejected; two stored school profiles keep separate tokens and caches; the app refuses a server address that is not in a verified profile. Manual: `./scripts/dev.sh mobile`, enter `DEMO`, log in.
- [ ] **P0-21b** **Mobile design foundation:** native UI kit in `owner/mobile/src/ui` built from the same tokens (buttons, inputs, list rows, cards, bottom tabs, sheet, toast, skeleton, empty and error states, school-picker styling), safe-area handling, 44/48 pt touch targets, dark mode, and three reference screens (list, form, dashboard). **Verify:** screenshots on a small and a large phone in light/dark and `en`/`am`; you review it against `docs/UI_CHECKLIST.md`, save the screenshots under `docs/review/p0/` and log it in `docs/OWNER_REVIEW.md`.
- [ ] **P0-22** **AI wiring stub:** `POST /api/v1/ai/chat` that echoes and lists the tools the user may use (no LLM yet), plus a chat panel on web. **Verify:** panel shows different tools for two different users.

### Document and delivery spike
- [ ] **P0-23** **PDF spike (decides the renderer):** render an HTML page containing Amharic (Ge'ez) text, Latin text, an embedded font and a QR code to PDF with Chromium/Playwright and with WeasyPrint. Compare shaping, embedding and speed. Choose one, record the decision in `docs/DECISIONS.md`, and expose `POST /api/v1/sample/pdf`. **Verify:** automated check that the PDF contains the embedded Ethiopic font, plus a manual visual check by opening the file.
- [ ] **P0-24** CI (GitHub Actions or equivalent): ruff, type check, pytest, Vitest, builds for web, controller web and mobile, API client generation diff check, i18n key check.
- [ ] **P0-25** **Dev launcher:** `scripts/dev.sh` and `scripts/dev.ps1` with `up`, `seed`, `reset`, `test`, `mobile`, `logs`, `down`. `seed` creates the controller owner, one enrolled demo instance (school code `DEMO`) and the demo accounts from section 1 (those relevant so far). It refuses to run in production. **Verify:** from a clean clone, `./scripts/dev.sh up && ./scripts/dev.sh seed` yields working logins at the ports listed in 0.5.
- [ ] **P0-26** **Smoke e2e (Playwright):** controller login → disable the `sample` module for the demo school → school login shows the menu without it → re-enable → "Open as school admin" → perform a sample change (the persistent controller-session banner is visible) → controller vault shows it labeled `via=controller`. Keep this test forever.

### ✅ CHECKPOINT P0
- [ ] `./scripts/dev.sh reset && ./scripts/dev.sh test` is fully green.
- [ ] Smoke e2e (P0-26) passes. The mobile app opens in Expo Go and logs in.
- [ ] Amharic text renders correctly in the PDF spike and in the web UI.
- [ ] The design foundation (P0-19b, P0-21b) is self-reviewed against `docs/UI_CHECKLIST.md` (clean, modern, consistent in light and dark and in Amharic), with screenshots saved and an `OWNER_REVIEW.md` entry. The owner's later review does not block progress.
- [ ] Every connection in the architecture diagram (ARCH §4.1) has been exercised by a test.
- [ ] `docs/PROGRESS.md` and `docs/DECISIONS.md` are current. Tag `v0.0-skeleton`.

**Owner test script after P0:** log in to the controller, toggle the sample module, switch the language to Amharic, switch themes, open the school as admin, check the vault.

---
## PHASE 1: Foundations (muscles for the core)

**Goal:** make everything modules will depend on production-quality. **Cites:** ARCH §5, §10.

### Platform conventions
- [ ] **P1-01** API conventions: pagination envelope, filtering/sorting helpers, standard error codes with `message_key`, `Idempotency-Key` middleware (24h store), optimistic concurrency via `row_version` (`409 CONFLICT`). **Verify:** tests for each, including replay of an idempotent request.
- [ ] **P1-02** Soft-delete base: default query filter, restore helper, partial indexes. **Verify:** deleted rows hidden, restorable, audited.
- [ ] **P1-03** Settings system: typed layered settings (code < central < instance), generated settings UI from module `settings_schema`, audit on change.

### Auth, users, roles
- [ ] **P1-04** Auth hardening: lockout, rate limits, password reset by email (Mailpit in dev) and SMS adapter stub, session list and revoke, cookie+CSRF for web, TOTP 2FA (enforceable per role). **Verify:** tests for lockout, refresh rotation reuse detection, 2FA enrollment and login.
- [ ] **P1-05** Full RBAC (ARCH §5.3): scopes, multiple roles, direct grants/denies, delegation with expiry, "cannot grant what you don't hold". **Verify:** permission-matrix test generated across all routes × seeded roles.
- [ ] **P1-06** Default roles seeded and editable (Super Admin, Director, Academic Head, Department Head, Registrar, Teacher, Homeroom Teacher, Accountant, HR Officer, Librarian, Parent, Student).
- [ ] **P1-07** **Roles and users UI (web):** create/edit roles with a permission matrix grouped by module, assign roles, invite users, deactivate. Menus react instantly to permission changes. **Verify:** Playwright: removing a permission hides a menu item for `limited@demo.school`.
- [ ] **P1-08** **Module management UI** for the Super Admin (Settings → Modules): toggle with dependency warnings, shows licensed vs enabled vs permitted state.

### Audit and history
- [ ] **P1-09** Audit complete: entry fields from ARCH §5.4, `via`/actor types, read-auditing for sensitive entities, nightly `verify_chain`, shipping retries with backoff.
- [ ] **P1-10** **Activity history UI (school):** filter by user, module, entity, date and action. Shows before/after diffs. Visibility controlled by `audit.activity.view` with scope. Super Admin's own actions hidden unless `audit.activity.view_admin_actions`. **Never** exposes technical logs. **Verify:** test that a user without the permission gets `PERMISSION_DENIED`, and that no endpoint returns Tier B data.
- [ ] **P1-11** **Rollback/restore:** `Revertible` protocol, rollback and restore endpoints and UI buttons for opted-in entities, with a reason. **Verify:** change → revert creates a new audit entry with `reverts_id`; original entry untouched.
- [ ] **P1-12** Controller audit vault UI: search across schools, chain status, alerts on gaps or hash mismatch, suspicious-pattern alerts (mass deletes, off-hours grade changes: configurable thresholds).

### People, names, dates, money
- [ ] **P1-13** **Person and name model** (ARCH §5.8): `persons`, three-part names in both scripts, `full_name`/`short_name` by locale, normalized search column, `pg_trgm` search, duplicate detection service. **Verify:** unit tests with Amharic and Latin names; searching "Abebe Kebede" finds "አበበ ከበደ" when both are stored.
- [ ] **P1-14** Name form component (web and mobile) with both script fields, a hint to fill both, and no "last name" anywhere.
- [ ] **P1-15** **Ethiopian calendar** package (TS) and module (Python): conversion both ways, formatting (Amharic/English month names), date-picker supporting EC/GC/both. **Verify:** test vectors checked against two independent authoritative sources (including leap-year new-year dates); round-trip property test over 100+ years.
- [ ] **P1-16** **Money** package and library (ETB, santim): parse, format, allocate with remainder handling, tests for rounding and large values.
- [ ] **P1-17** Custom fields engine: definitions per entity, JSONB values, validation by type, visibility by role, rendered automatically in forms.

### i18n, themes, files, notifications
- [ ] **P1-18** **Translation Editor** (ARCH §5.6): table, search, module filter, missing/needs-review filters, edit inline, import/export CSV/JSON, layers (school override vs central), in-context edit mode, audit. **Verify:** edit an Amharic label in the editor and see it change in the web and mobile apps without redeploy.
- [ ] **P1-19** "Suggest with AI" hook in the editor (calls the action registry; works once the AI module exists in Phase 9; until then returns a clear "AI not configured" state). Drafts are `needs_review`.
- [ ] **P1-20** i18n tooling: lint rule banning hard-coded UI strings, CI check for missing `en` keys, report for missing `am` keys, Ethiopic font bundled for web and mobile.
- [ ] **P1-21** **Theme Manager** (ARCH §5.11): import by CSS paste, JSON upload and registry URL; validation (both modes, chart and sidebar tokens, contrast checks); preview; per-school available themes; per-user choice; mobile theme object generated from the same tokens. **Verify:** a theme with an unreadable color pair is rejected with a clear reason; a broken theme falls back to default.
- [ ] **P1-22** Files service: S3 storage, signed URLs, validation, thumbnails job, `files` table, upload component.
- [ ] **P1-23** Notification service: in-app, email (SMTP), push (sent through the controller push relay, ARCH §8.11; a logging stub until P11-12) and SMS adapter interface; templates with variables; delivery logs; user notification center UI.
- [ ] **P1-24** Instance setup wizard: school profile, logo, calendar display, default language, grade scope placeholder, theme, first Super Admin.
- [ ] **P1-25** Jobs UI: list of background jobs with progress, retry, errors (user-safe).
- [ ] **P1-26** **API compatibility guard** (ARCH §8.10): snapshot the OpenAPI schema per release and fail CI on breaking changes within `/api/v1` (removed or renamed fields or endpoints, narrowed types, new required request fields). Policy: additive only; deprecations stay for at least two releases. **Verify:** a deliberately breaking change fails the check.
- [ ] **P1-27** **UI quality gate automation:** Playwright screenshot tests for the reference and key screens at 1440, 768 and 390 widths in light and dark and in `en` and `am` (with a long-Amharic-text fixture); an automated accessibility scan (axe) failing on serious violations; a check that every data screen implements loading, empty and error states; theme import check that a community theme cannot break layout. **Verify:** a deliberately low-contrast theme and a screen missing its empty state both fail the gate.
- [ ] **P1-SEED** Update seed: all roles, accounts from §1 (roles assigned), a custom limited role, sample translation overrides, themes, sample audit history.

### ✅ CHECKPOINT P1
- [ ] All tests green. Permission matrix test covers every route.
- [ ] Owner script: log in as each role and confirm different menus. Change a permission and see the menu change. Edit an Amharic label. Import a theme. View activity history as Super Admin. Roll back a change. See it in the controller vault.
- [ ] Tag `v0.1-foundations`.

---

## PHASE 2: Academic structure, students and admissions

**Cites:** ARCH §9.1, §9.2.

- [ ] **P2-01** Module `academics`: grade levels catalog (KG1–Grade 12 default, editable), stages, **school scope** (`first_level`, `last_level`) with validation. **Verify:** setting scope to Grade 1–5 removes other levels from every dropdown (test via API listing).
- [ ] **P2-02** Academic years and terms (semester or quarter chosen per school), open/close, EC/GC display.
- [ ] **P2-03** Sections (per level per year, homeroom teacher, capacity), subjects, level-subject assignment, subject groups.
- [ ] **P2-04** Curriculum profiles: model, shipped starter templates (*Ethiopian National*, *Private: Custom*, *International: Generic*) marked **unverified starter data**, duplicate and edit, apply from a chosen year.
- [ ] **P2-05** Academics UI (web): setup screens for scope, years/terms, sections, subjects, curriculum profile. Include the setup wizard steps.
- [ ] **P2-06** Module `students`: `student_profiles`, `enrollments`, guardians (many-to-many), medical record, documents, custom fields, statuses. Actions registered (`students.register`, `students.update`, `students.search`, …) with previews.
- [ ] **P2-07** Student ID generator with configurable format, atomic sequence. **Verify:** concurrent test produces no duplicates.
- [ ] **P2-08** Students UI (web): list with search, filters and saved views, profile page, registration form (three-part names, both scripts), guardian linking, photo upload, document upload, duplicate warning.
- [ ] **P2-09** Module `admissions`: configurable application form (custom fields), documents, optional entrance test score, decision workflow, auto-assignment rule to level/section, conversion of applicant → student, guardian account creation.
- [ ] **P2-10** Admissions UI and public application page (optional, toggle) with spam protection.
- [ ] **P2-11** Promotion and transfer: bulk promotion preview and apply (manual exceptions; rules plug in at Phase 4), transfer-out, withdrawal, graduation, alumni. All reversible through audit rollback where applicable.
- [ ] **P2-12** Mobile: student directory (read), student profile (permission-scoped), registration form (online only).
- [ ] **P2-13** Events: `student.admitted`, `student.enrolled`, `student.promoted` emitted through the outbox.
- [ ] **P2-SEED** Seed: academic year in semester mode, levels 1–8 (+KG), sections, subjects, ~60 students with realistic Ethiopian three-part names (Amharic + Latin), guardians (parent1 has two children), staff placeholders.

### ✅ CHECKPOINT P2
- [ ] Tests green, including scope tests (a Grade 1–5 school exposes nothing above Grade 5).
- [ ] Owner script: register a student with Amharic and Latin names, see duplicate warning, promote a section, change school scope and watch dropdowns shrink, roll back a deletion.
- [ ] Tag `v0.2-students`.

---

## PHASE 3: Staff, HR and attendance

**Cites:** ARCH §9.3, §9.4.

- [ ] **P3-01** Module `staff`: staff profiles on `persons`, departments, positions, contracts, qualifications, documents; link to user accounts.
- [ ] **P3-02** **Teaching assignments** (teacher ↔ subject ↔ section ↔ year) and the scope resolvers `assigned_subjects`, `own_class`, `department`. **Verify:** teacher1 cannot read Grade 6 data; teacher2 cannot read Grade 5 data.
- [ ] **P3-03** Leave: types, balances, requests, approval workflow, calendar view.
- [ ] **P3-04** Staff UI (web) and basic mobile directory.
- [ ] **P3-05** Optional payroll sub-module: salary components, payslips in ETB, **configurable** tax and pension rules (no hard-coded rates), payslip PDF through the (later) Document Studio, so only the data model and calculation engine are built now. Mark rules as "to be validated by an accountant."
- [ ] **P3-06** Module `attendance`: daily and per-period modes (per-period activates with timetable), sessions and records, statuses, fast entry (default present).
- [ ] **P3-07** Attendance UI (web grid) and **mobile quick entry with offline outbox**. **Verify:** mark attendance offline, reconnect, see exactly one record per student (idempotency).
- [ ] **P3-08** Staff attendance, absence events (`attendance.absent_marked`), reports (by student, section, threshold).
- [ ] **P3-SEED** Seed: teachers with assignments, a week of attendance, leave requests.

### ✅ CHECKPOINT P3
- [ ] Tests green, including offline sync test.
- [ ] Owner script: log in as each teacher and confirm scope isolation. Mark attendance on a phone with airplane mode on, then sync.
- [ ] Tag `v0.3-staff-attendance`.

---

## PHASE 4: Assessment: marks, grade rules, results

**Cites:** ARCH §9.5, §11.3, §11.4. This is the most logic-heavy phase. Build the **pure engine first** with exhaustive tests.

### Engine (pure, no database)
- [ ] **P4-01** `assessment/engine.py`: percent conversion, aggregation modes (`average`, `weighted_average`, `best_n`, `sum_capped`, `latest`), absent/excused/exempt/not-taken handling, rounding (mode and precision), term total, year rule. **Verify:** table-driven tests including: 12/15 → 8.0/10; second quiz 9/13 → 6.9/10; averaging them; absent counted as zero vs excluded; raw > out_of rejected unless bonus; extreme decimals.
- [ ] **P4-02** **Grade rule engine:** band resolution on half-open ranges, validation (full coverage, no gaps, no overlap, sorted), descriptive scales, scale assignment resolution (assessment context > subject > level > stage > default), versioning. **Verify:** tests for boundary values (e.g. exactly 75, 74.99, 100, 0), user-defined bands like 75–<85 → C+, and invalid band sets rejected with clear errors.
- [ ] **P4-03** Rank (tie handling options) and **promotion rules** (min average, max failed subjects, per-subject minimums). Plug into the promotion flow from P2-11.

### Data and APIs
- [ ] **P4-04** Models and migrations for structures, components, assessments, scores, score revisions, term results, result snapshots, grade scales and bands, assignments, windows, submissions, correction requests.
- [ ] **P4-05** Structure management APIs and actions: create/edit structure per school/stage/level/subject and year with preview of impact; **recalculation job** when a structure changes (raw data untouched). **Verify:** change a component max → converted values update, raw values identical, audit entry written.
- [ ] **P4-06** Assessment and score APIs: create assessment (`out_of`, component), bulk score upsert with validation, scoping by teaching assignments, row-versioning, idempotency.
- [ ] **P4-07** Workflow APIs: marking windows, submit, approve, publish, lock, correction requests and approvals. State machine tests (illegal transitions rejected).
- [ ] **P4-08** Results: term and year results, ranks, publish snapshots storing the scale version used, **re-publish** as an explicit audited action.
- [ ] **P4-09** Events: `marks.submitted`, `marks.published`, `term.closed`.

### UI
- [ ] **P4-10** **Mark structure UI** (academic head/director): components, maxima, aggregation, year rule, rounding, descriptive mode for KG. Shows total and warns if components do not add up to the intended total.
- [ ] **P4-11** **Grade rules UI:** scale list, band editor ("from X to Y" with auto-adjusted neighbors and live validation), default scale, per-context assignments, and the **test tool** (type a score, see the label).
- [ ] **P4-12** **Web mark-entry grid** (ARCH §11.3): keyboard navigation, status keys, live converted preview, footer statistics, autosave with status, conflict handling, Excel paste, template download/upload with a validation preview, read-only state for locked windows with "request correction". **Verify:** Playwright test enters 30 marks using only the keyboard and a pasted column.
- [ ] **P4-13** **Mobile mark entry:** card mode and list mode, numeric keypad, auto-advance, offline outbox, per-row sync status, conflict resolution step. **Verify:** enter marks offline for a section, reconnect, no duplicates, correct converted values.
- [ ] **P4-14** Manager dashboard: completion per section/teacher, overdue list, automatic reminders (notification templates), anomaly flags.
- [ ] **P4-15** Approvals UI (department/academic head): review submitted marks, approve/reject with comment, publish.
- [ ] **P4-16** Parent and student read views of **published** results only (web and mobile). Unpublished data never leaves the API.
- [ ] **P4-17** Register assessment actions (`assessment.enter_marks`, `assessment.publish`, …) with previews so the AI layer can use them later, and register the document fields (`student.marks.*`, `student.rank`, …) for Document Studio.
- [ ] **P4-SEED** Seed: a mark structure (components totaling 100), a default grade scale with a custom C+ band, a second scale for "official exam", sample assessments out of 15 and 13, a published term for one section.

### ✅ CHECKPOINT P4
- [ ] Engine tests exhaustive and green. Property tests: converted value always within `[0, component.max]`, recalculation is idempotent.
- [ ] Owner script: as academic head define components and grade bands (e.g. 75–<85 → C+); as teacher1 enter marks out of 15, then out of 13; see converted values; submit; approve; publish; change a band and see labels change but raw marks untouched; as teacher request a correction after lock; as parent see only published results.
- [ ] Performance: entering marks for a 60-student section feels instant. Recalculation of a 3,000-student term completes as a background job within an acceptable time (record the number in `DECISIONS.md`).
- [ ] Tag `v0.4-assessment`.

---
## PHASE 5: Document Studio

**Cites:** ARCH §9.8. Use the renderer chosen in P0-23.

- [ ] **P5-01** Layout JSON schema (elements, positions in mm, styles, bindings, conditions, repeating tables), versioned, validated with Pydantic and Zod from one shared definition. **Verify:** schema round-trip tests; invalid layouts rejected.
- [ ] **P5-02** **Fields registry:** modules register fields (`fields.py`), `GET /api/v1/documents/fields` returns only fields from enabled modules. Formatting options: calendar (EC/GC/both), script (am/en), money (ETB).
- [ ] **P5-03** Renderer: layout + data → HTML/CSS → PDF. Bundled Ethiopic fonts, uploaded fonts, QR and barcode support, page presets and custom sizes, bleed. **Verify:** golden-file tests (render known layout and compare key properties and text extraction); Amharic text present and font embedded.
- [ ] **P5-04** Template models: `doc_templates`, `doc_template_versions`, draft/publish, duplicate, import/export as a file, starter library (report card, certificate of completion, certificate of appreciation, ID card, admission letter, receipt, experience letter).
- [ ] **P5-05** **Canvas editor (web):** drag/drop elements, text, image, shape, line, table, QR/barcode, logo, signature/stamp/photo placeholders, field insertion panel, alignment, snap, layers, undo/redo, zoom, page setup. **Verify:** Playwright creates a certificate, inserts `{{student.full_name}}`, saves, and previews.
- [ ] **P5-06** Repeating tables (subjects × components/terms) with totals, average, rank, attendance, remarks. Conditional blocks ("Promoted"/"Repeat").
- [ ] **P5-07** Preview with sample or real data (choose a student) before publishing, using the same renderer as production.
- [ ] **P5-08** **Generation:** single and bulk (section, grade) as separate files or one combined PDF through background jobs with progress. `issued_documents` store template version and a **data snapshot**, number, issuer, date. **Verify:** reprint after a data change reproduces the original; bulk run of 300 documents completes without blocking the API.
- [ ] **P5-09** Public verification page `/verify/{code}` showing only minimal data, rate-limited.
- [ ] **P5-10** Permissions and workflow: separate `documents.template.design`, `documents.generate`, `documents.approve`; optional approval before issuing certificates; audit of design changes and issuance.
- [ ] **P5-11** Wire existing modules: report cards and transcripts from assessment, receipts from fees (once Phase 7 exists the receipt template is connected then), ID cards from students, staff experience letters from staff.
- [ ] **P5-12** Mobile: view, share and print issued documents (generation on web only).
- [ ] **P5-SEED** Seed: starter templates, a published certificate and report card template, a generated batch for one section.

### ✅ CHECKPOINT P5
- [ ] Tests green. Visual check by the owner of printed PDFs in Amharic and English.
- [ ] Owner script: design a custom certificate on the canvas, generate for one student, then bulk for a section, scan the QR code to verify, change the template and confirm old documents are unchanged.
- [ ] Tag `v0.5-documents`.

---

## PHASE 6: Timetable

**Cites:** ARCH §9.6.

- [ ] **P6-01** Models: rooms, period definitions, availability, subject loads, constraints, versions, slots, substitutions.
- [ ] **P6-02** **Solver in isolation:** OR-Tools CP-SAT model with hard constraints (no double booking of teacher/room/section, availability, room capacity/type, weekly loads) and weighted soft constraints (spread, gaps, double periods). Pure function from input JSON to slots. **Verify:** tests with small fixtures where the optimum is known; infeasible fixture returns an explainable reason.
- [ ] **P6-03** Background generation job with time limit and progress, versioned drafts, failure explanations in plain language.
- [ ] **P6-04** Timetable UI: constraint setup screens, grid view per section/teacher/room, **drag-and-drop editing with live conflict checks**, lock slots before regenerating, publish a version.
- [ ] **P6-05** Substitute-teacher flow tied to staff leave/absence.
- [ ] **P6-06** Outputs: web views, mobile views for teachers/students/parents, printable PDFs via Document Studio.
- [ ] **P6-07** Switch attendance to per-period mode when configured. **Verify:** attendance sessions follow the published timetable.
- [ ] **P6-SEED** Seed: rooms, periods, loads, a generated and published timetable for the demo school.

### ✅ CHECKPOINT P6
- [ ] Tests green. Solver completes a large-school fixture (e.g. 60 sections, 100 teachers) within the recorded time budget.
- [ ] Owner script: generate a timetable, drag a lesson into a conflict and see the warning, publish, view as a teacher on mobile.
- [ ] Tag `v0.6-timetable`.

---

## PHASE 7: Fees and payments

**Cites:** ARCH §9.7, §5.9. All money in santim.

- [ ] **P7-01** `shared/py/payments.py`: provider interface (`create_checkout`, `verify`, `handle_webhook`, optional `refund`), event model, status enum, signature-verification helpers, and a **sandbox test double** used in tests.
- [ ] **P7-02** Fee models: items, structures per level/year, schedules (monthly/term/yearly/custom), discounts and scholarships (with approval), late-fee rules.
- [ ] **P7-03** Invoice generation (single, bulk by section/level), numbering, lines, status machine, credits.
- [ ] **P7-04** Payments, allocations (one payment → several invoices), receipts (numbered; receipt template via Document Studio), refunds. **Verify:** property tests: allocations sum to payment, invoice balances never negative, rounding remainders handled.
- [ ] **P7-05** **Manual bank adapter:** parent submits reference and optional slip image; accountant verifies/rejects; reconciliation view. **Cash adapter:** counter receipts.
- [ ] **P7-06** Gateway adapters as **disabled stubs with sandbox-ready code** for Chapa, ArifPay, SantimPay, telebirr and CBE Birr, plus a note for EthSwitch. For each: **before coding, read the provider's current official docs, record the findings and its current regulatory/operational status in `docs/DECISIONS.md`**. Credentials entered in settings (encrypted). Webhook endpoint with signature verification and idempotency. Status polling fallback. Re-verify amount/currency with the provider on every callback. **Verify:** using the test double and recorded fixtures: valid, tampered, replayed and underpaid webhooks.
- [ ] **P7-06b** Multi-provider support: more than one provider active at once, parent chooses at checkout, school sets which are offered.
- [ ] **P7-07** Arrears dashboard, reminder automation hooks (`invoice.overdue`), accountant reports (collections, outstanding, by level, by method), CSV/Excel export.
- [ ] **P7-08** Fees UI (web) for accountant; parent portal fee view and "pay" flow (web and mobile). Payments are online-only (never queued offline).
- [ ] **P7-09** ETB shown everywhere via the money layer. Tax settings are configuration fields (no constants).
- [ ] **P7-SEED** Seed: fee structure, invoices for the demo students, a few payments (manual), one overdue invoice.

### ✅ CHECKPOINT P7
- [ ] Tests green, including all webhook edge cases against the test double.
- [ ] Owner script: generate invoices for a section, record a bank payment as parent, verify as accountant, print the receipt, see arrears.
- [ ] Tag `v0.7-fees`.

---

## PHASE 8: Communication and portals

**Cites:** ARCH §9.9, §5.5.

- [ ] **P8-01** Announcements: audience targeting, scheduling, attachments, translatable content variants (preview/save flow stubbed until Phase 9).
- [ ] **P8-02** Parent–teacher messaging with configurable moderation, per-thread permissions, no cross-family leakage. **Verify:** IDOR tests on every message endpoint.
- [ ] **P8-03** Notification templates UI, channel preferences per user, delivery logs, SMS and push adapters wired (SMS provider remains a stub until chosen).
- [ ] **P8-04** Parent portal (web + mobile): children switcher, published marks and report cards, attendance, timetable, fees and payment, announcements, issued documents.
- [ ] **P8-05** Student portal with the appropriate subset.
- [ ] **P8-06** Push notifications on mobile through the controller push relay (ARCH §8.11) with minimal payloads, and deep links into the right screen.
- [ ] **P8-SEED** Seed: announcements, message threads, parent1 with two children.

### ✅ CHECKPOINT P8
- [ ] Tests green, including cross-family isolation tests.
- [ ] Owner script: send an announcement to one grade, see it on the parent's phone, reply in a thread, open a report card.
- [ ] Tag `v0.8-portals`.

---

## PHASE 9: AI layer

**Cites:** ARCH §6, §7, §5.6. Use only official provider documentation for current model names and APIs. Model names are settings, never constants.

- [ ] **P9-01** `core/ai`: `LLMProvider` interface and adapters for Anthropic, OpenAI and Google (chat, tool calling, streaming). Contract tests against recorded fixtures plus a fake provider for CI.
- [ ] **P9-02** AI settings: provider, model name, key entry (AES-GCM encrypted, masked display, never returned), limits, per-school token counters, CP kill switch. **Verify:** key never appears in any API response or log.
- [ ] **P9-03** **Complete the action registry coverage:** every module registers its useful actions with `risk`, `preview()` and `ai_forbidden` where needed (roles, permissions, AI keys, audit settings, module toggles are forbidden). A test lists all registered actions and fails if one lacks a permission or risk level.
- [ ] **P9-04** **Orchestrator:** builds the tool list (enabled ∩ permitted ∩ not forbidden), runs the model loop with a step limit, runs `read` actions directly, turns others into `ai_proposals` with previews, executes on confirmation as the user with `via=ai`, bulk threshold confirmation showing counts. **Verify:** a user without `students.record.create` cannot create a student via the AI even if asked directly.
- [ ] **P9-05** **Prompt-injection defenses:** untrusted-data delimiting for all tool outputs and stored text, red-team test suite (hostile student note or uploaded text that tells the AI to delete data or grant roles must have no effect). **Verify:** the suite runs in CI against the fake provider with scripted malicious model outputs.
- [ ] **P9-06** Chat UI (web and mobile): streaming, proposal cards with preview and confirm/cancel, history, "executed via AI" labels linking to audit entries.
- [ ] **P9-07** **Voice input:** device/browser speech recognition with transcript shown for correction before running, typed fallback always available. Check and record Amharic recognition support per platform in `DECISIONS.md`. Optional provider-based STT/TTS behind an adapter.
- [ ] **P9-08** **Natural-language reports** via parameterized report actions (attendance below X, students with arrears, marks distribution…). No free-form SQL anywhere.
- [ ] **P9-09** **Content translation:** preview-then-save flow for free-text fields (announcements, comments, messages, template wording) into `content_translations` with source `ai`, status `needs_review`, never overwriting originals. UI shows the original and each language variant. The "Suggest with AI" translation drafts in the Translation Editor (P1-19) now work.
- [ ] **P9-10** Name transliteration suggestion (needs human confirmation), report-card comment drafts, at-risk student alerts (rule-based signals first, AI summary second).
- [ ] **P9-11** AI usage and cost view, rate limits, audit of AI sessions.
- [ ] **P9-SEED** Seed: AI module enabled with the **fake provider** so the owner can test the flow without a key; instructions to add a real key in settings.

### ✅ CHECKPOINT P9
- [ ] Tests green including the injection suite and permission-bound AI tests.
- [ ] Owner script: add a real API key, say "Register a student …" and confirm the preview card; try the same as `limited@demo.school` and see the refusal; ask for attendance below 80% this month; translate an announcement to Amharic, review it, save it.
- [ ] Tag `v0.9-ai`.

---

## PHASE 10: Automation engine

**Cites:** ARCH §9.10.

- [ ] **P10-01** Rule model (trigger, JSON-logic conditions, action list, optional delay, schedule triggers), validation against the event and action registries.
- [ ] **P10-02** Engine: subscribes to the outbox, evaluates conditions, runs actions as an `automation` actor limited to the rule's `run_as` permissions, loop/recursion guards, run history with outcomes, retry policy.
- [ ] **P10-03** **Dry-run mode** showing what would happen without executing.
- [ ] **P10-04** Rule builder UI: pick a trigger, add conditions with a friendly editor, add actions (including notifications), test with sample data, enable/disable.
- [ ] **P10-05** Starter rules shipped disabled: admitted → account + class + welcome + invoice; absence → notify guardian; marking deadline → remind teacher; term closed → compile report cards + notify parents; invoice overdue → reminder.
- [ ] **P10-SEED** Seed: starter rules visible; one enabled (absence → guardian notification).

### ✅ CHECKPOINT P10
- [ ] Tests green, including a rule that tries to trigger itself being stopped.
- [ ] Owner script: mark a student absent and see the parent notification fire; dry-run the admission rule.
- [ ] Tag `v0.10-automation`.

---
## PHASE 11: Control Plane completion

**Cites:** ARCH §8, §9 (CP tables in §10).

- [ ] **P11-01** CP users and roles (Owner, Support, Billing, Read-only), mandatory 2FA, audit of CP actions.
- [ ] **P11-02** Plans and subscriptions: plans with included modules and limits; per-school subscription with module toggles; license issuing and renewal on schedule; statuses `active | grace | suspended` with the **kill switch**. **Verify:** suspended instance behaves per policy; offline instance keeps working through grace and then restricts.
- [ ] **P11-03** **Provisioning:** `deploy/provisioning` scripts (create compose project, env, DB, bucket, domain, enroll, seed an initial Super Admin). One command or CP button per new school. **Verify:** provision a brand-new second instance on the same host and see both run in isolation.
- [ ] **P11-04** Instance size profiles (`small|standard|large`) applied at provisioning.
- [ ] **P11-05** Monitoring dashboard: per-school uptime, version, errors, queue depth, DB/storage use, counts, last backup, AI usage. Alert rules (heartbeat missing, backup failed, chain break, error spike).
- [ ] **P11-06** Audit vault oversight: full search, chain verification, suspicious-activity alerts (already started in P1-12), export.
- [ ] **P11-07** **Support sessions** hardened: reason required, optional read-only mode, expiry, list of past sessions, per-school notification policy.
- [ ] **P11-08** Version management: register releases, staged rollout (pilot school first), per-school upgrade status, upgrade runbook script (backup → pull → migrate → health check → rollback by restore).
- [ ] **P11-09** **Your business revenue in ETB:** school invoices (subscription fees), payments (manual first, gateway adapters reusing `shared/py/payments.py`), MRR/ARR, per-school revenue, overdue subscriptions, reports for monthly/yearly in ETB.
- [ ] **P11-10** Central push of translations (central layer), themes, and Document Studio templates to selected or all schools.
- [ ] **P11-11** Backups visibility and restore tooling documented and tested (see Phase 14).
- [ ] **P11-12** **Push relay** (ARCH §8.11): the mobile app registers a device token with the controller for a (school, user pseudonym) pair; instances send signed `POST /push/send` requests; the controller delivers via the push provider (Expo push or FCM/APNs). Minimal payloads (no marks, names or amounts) plus a deep link. Token cleanup, per-school rate limits, delivery log. **Verify:** with a fake push provider, a school cannot push to a device registered under another school; a revoked device receives nothing.
- [ ] **P11-13** **Directory hardening:** school-code generation, rotation and revocation in the CP UI; QR generation and printing for onboarding; name search off by default (optional per school); `kid`-based key rotation with the app accepting a key set; enumeration protection; suspended-school behavior. **Verify:** brute-forcing codes is throttled; a revoked code stops resolving.
- [ ] **P11-SEED** Seed: two plans, two enrolled demo instances running side by side (code `DEMO` active, code `DEMO2` in grace), sample subscription invoices.

### ✅ CHECKPOINT P11
- [ ] Tests green. Provisioning script tested end to end.
- [ ] Owner script: create a plan, provision a new school, enable specific modules, suspend and reactivate it, push a central translation, view revenue in ETB.
- [ ] Tag `v0.11-controller`.

---

## PHASE 12: The single multi-school mobile app: completion and hardening

**Cites:** ARCH §11.2–11.4.

- [ ] **P12-01** Audit every mobile screen against the web feature list for roles that use mobile (teacher, staff, parent, student). Fill gaps in `docs/DECISIONS.md` as explicit "web only" or build them.
- [ ] **P12-02** Outbox hardening: queue states, retry with backoff, idempotency keys, base `row_version`, conflict resolution screens, "online only" guards for unsafe actions.
- [ ] **P12-03** Offline test suite: airplane-mode scenarios for attendance, marks, messages; kill app mid-sync; duplicate prevention; clock skew.
- [ ] **P12-04** Push notifications end to end, deep linking, notification preferences.
- [ ] **P12-05** Mobile performance and UX pass: list virtualization, image caching, startup time, small-screen layouts, Amharic text overflow, dark mode.
- [ ] **P12-06** EAS build profiles (development, preview, production), app config, icons, splash, versioning, OTA update channel. Document the release process in `docs/runbooks`.
- [ ] **P12-07** **Multi-school accounts:** add and remove schools, account switcher, per-school isolated storage for tokens, cache and outbox (removing a school wipes its local data), optional biometric/app lock, remembering the last school. **Verify:** a user with accounts in `DEMO` and `DEMO2` switches between them with no data bleed (test), and a queued offline action can never be sent to the wrong school.
- [ ] **P12-08** **Version handshake** (ARCH §8.10): on opening a school, read `/system/info`; enforce `min_client_version` with a clear update screen; hide features missing from `/system/capabilities`; show a gentle "school is on an older version" state. **Verify:** compatibility tests against stored API fixtures from the previous release and a simulated newer server.
- [ ] **P12-09** **Release of the single app:** one EAS project, store listings (the owner supplies Apple Developer and Google Play accounts), app signing, an OTA-update policy (compatible JS updates only), crash reporting, privacy labels. Document in `docs/runbooks/release-mobile.md`.
- [ ] **P12-10** **White-label hook (do not build the feature):** keep a build-time variant mechanism (`APP_VARIANT` for name, icon, fixed school code) documented in `docs/DECISIONS.md`, so a branded per-school app could be added later without refactoring.
- [ ] **P12-SEED** Make sure demo data exercises mobile flows.

### ✅ CHECKPOINT P12
- [ ] Tests green. Owner script on a real phone via Expo Go: attendance and marks offline then sync, push notification, switch to Amharic, switch themes.
- [ ] Tag `v0.12-mobile`.

---

## PHASE 13: Add-on modules (optional, one at a time)

Build only those listed in `docs/OWNER_REQUESTS.md`. If the file is empty or missing, skip this phase and continue to Phase 14. Each must be a **self-contained module** (manifest, permissions, i18n, document fields, actions, tests) that passes the module-conformance test.

- [ ] **P13-00** Create the **module conformance test** (checks manifest completeness, permissions declared, actions have risk levels, i18n keys exist for `en`, migrations carry the module branch label, no cross-module table imports).
- [ ] **P13-01** Library (catalog, borrowing, fines in ETB).
- [ ] **P13-02** Transport (routes, stops, vehicles, student assignment, fees link).
- [ ] **P13-03** Inventory.
- [ ] **P13-04** Hostel.
- [ ] **P13-05** Health clinic (strict permissions, read-audit).
- [ ] **P13-06** Events.

### ✅ CHECKPOINT P13
- [ ] Each built add-on can be toggled on/off per school with no side effects when off. Tag `v0.13-addons`.

---

## PHASE 14: Hardening and production readiness

**Cites:** ARCH §12, §13, §14.

### Security
- [ ] **P14-01** Security review against ASVS L2 checklist; fix findings. Security headers, CORS, CSRF, rate limits verified by tests.
- [ ] **P14-02** **IDOR test sweep:** every ID-based endpoint tested as a different-scope user. Automate with the permission matrix.
- [ ] **P14-03** Secrets handling review: nothing in git (scan history), encryption keys rotation procedure documented and tested, AI key and payment credentials encrypted at rest.
- [ ] **P14-04** Dependency and container vulnerability scanning in CI; lockfiles pinned; policy against very recently published versions.
- [ ] **P14-05** Data protection: retention settings, export/delete workflows for personal data (soft delete plus controlled purge procedure documented), read-audit on sensitive entities, privacy notice templates. **List remaining legal items for the owner to review with a local lawyer.**

### Performance and reliability
- [ ] **P14-06** Load tests (k6/Locust) at the large-school scale: ~3,000 students, concurrent teachers entering marks, parents viewing results at publish time, bulk PDF generation of 3,000 report cards, timetable solve. Record results and tune (indexes, caching, worker concurrency). Define the three size profiles from measured numbers.
- [ ] **P14-07** Database review: indexes, slow-query log, `EXPLAIN` on the heaviest queries, pagination everywhere.
- [ ] **P14-08** Failure tests: Redis down, storage down, CP unreachable (grace behavior), DB failover/restart, worker crash mid-job (jobs resume or fail visibly).

### Operations
- [ ] **P14-09** **Backups:** nightly encrypted DB dump plus storage sync, retention, status reported in heartbeats. **Restore drill performed and documented**, restoring a backup into a fresh instance and verifying data and audit chain.
- [ ] **P14-10** Production compose files (`deploy/compose/instance.yml`, `controller.yml`), Caddy with automatic TLS, resource limits per size profile, log rotation, secret handling, `.env.production.example`.
- [ ] **P14-11** Observability: structured logs, optional error reporting, metrics for heartbeats, uptime checks.
- [ ] **P14-12** Runbooks in `docs/runbooks`: provision a school, upgrade, rollback, restore, rotate keys, suspend/reactivate, investigate a chain alert, onboard a payment provider, release a mobile build.
- [ ] **P14-13** Full visual review of every screen against `docs/UI_CHECKLIST.md` (spacing, states, consistency), plus accessibility and i18n pass: keyboard-only walkthrough of key flows, contrast checks across shipped themes, Amharic overflow check on all screens, missing `am` key report delivered to the owner for translation.
- [ ] **P14-14** Documentation: admin guide, teacher quick-start, registrar guide, parent guide (English and Amharic drafts clearly marked for human review).

### ✅ CHECKPOINT P14
- [ ] All tests, security checks and load tests pass and recorded. Restore drill passed.
- [ ] A **production-like staging** deploy of one instance plus the controller succeeds from scripts alone, with the seed script correctly **refusing** to run.
- [ ] Tag `v1.0-rc1`.

---

## PHASE 15: Final dev launcher, seed and release

- [ ] **P15-01** Consolidate `scripts/dev.sh` and `dev.ps1`: `up | seed | reset | test | mobile | logs | down | smoke`. `smoke` runs the full smoke e2e suite. Ensure a fresh clone works with Docker only (plus Node/pnpm and Python/uv if running outside containers). Document prerequisites in `README.md`.
- [ ] **P15-02** **Final seed:** everything built across all phases (all demo accounts in section 1 of this guide, realistic Ethiopian data in Amharic and Latin, timetable, marks, fees, documents, automation rules, AI fake provider, two controller-enrolled instances). Refuses `APP_ENV=production`.
- [ ] **P15-03** `README.md` and `docs/OWNER_TEST_GUIDE.md`: a per-role click-through script (what to log in as, what to try, what you should see) covering every module, written for a non-developer.
- [ ] **P15-04** Full regression: `./scripts/dev.sh reset && ./scripts/dev.sh test && ./scripts/dev.sh smoke` all green from a clean clone.
- [ ] **P15-05** Version tags, changelog, release notes, EAS production build instructions, first-school onboarding checklist (provision → enroll → setup wizard → choose scope/curriculum/term system → set mark structure and grade rules → create roles → import students → train staff).
- [ ] **P15-06** Final review of `docs/DECISIONS.md` and `docs/QUESTIONS.md`: produce a summary for the owner of every open item (payment credentials, SMS provider, legal review, translations to review, curriculum starter data to verify).
- [ ] **P15-07** **Optional: repo split rehearsal** (only if the owner asks to split). Write `docs/runbooks/split-repo.md` and verify it in a scratch copy: `school-erp/` + `shared/` become one repo, `owner/` + `shared/` another; `shared/` is published as versioned private packages (a Python wheel and an npm package, or tagged git dependencies); the OpenAPI schema is published as a release artifact that `owner/` consumes; each repo has its own CI. **Verify:** both scratch repos build and pass their tests (the boundary checks already being green proves there is no hidden coupling). Do **not** perform the real split unless instructed in `docs/OWNER_REQUESTS.md`.

### ✅ FINAL CHECKPOINT
- [ ] `./scripts/dev.sh up && ./scripts/dev.sh seed` gives a fully working demo with all accounts in section 1.
- [ ] Zone boundary checks and the API compatibility guard are green.
- [ ] Every ARCH requirement is either implemented and tested, or listed in `docs/DECISIONS.md` with a reason.
- [ ] Production deployment procedure verified. Tag `v1.0.0`.

---

## Appendix A: Module conformance checklist (applies to every module)

- [ ] Manifest complete: key, version, dependencies, permissions with scopes, nav, settings schema, i18n namespaces, document fields, actions, events.
- [ ] Migrations with the module's branch label. No cross-module table imports.
- [ ] Every route declares a permission. Every mutation audited. Every action has `risk` and (if not read) `preview()`.
- [ ] `en` strings complete, `am` strings drafted and marked for review.
- [ ] Gated correctly: off → menu hidden, API `403 MODULE_DISABLED`, data preserved. On again → everything restored.
- [ ] Tests: logic, API, permission matrix, module toggle.
- [ ] Web and (where relevant) mobile screens registered through `module-sdk`.

## Appendix B: Owner's quick test routine after any phase

1. `./scripts/dev.sh up` then `./scripts/dev.sh seed`.
2. Controller at http://localhost:5174: sign in as `owner@controller.local`.
3. School at http://localhost:5173: sign in as the role being tested (section 1).
4. Mobile: `./scripts/dev.sh mobile`, scan the QR code with Expo Go, then enter the school code `DEMO` and log in.
5. Report anything that fails. Reset any time with `./scripts/dev.sh reset`.

## Appendix C: If you get stuck

- Re-read the cited ARCH sections and the task's **Verify** line.
- Reduce the problem: write the smallest failing test first.
- Do not rewrite unrelated code. Do not skip the task. Record the blocker in `docs/QUESTIONS.md` and continue with another independent task.
