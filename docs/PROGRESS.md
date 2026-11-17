# Build progress

Follow `02_BUILD_GUIDE.md` in order. Tick a task only when its **Verify** step passes.
Commit format: `P{phase}-{nn}: short description`.

Last verified: 2026-11-17 (see "Phase 0 verification" at the end of this section).

## Phase 0 — Walking skeleton

- [x] P0-01 Repository, workspaces, tooling, env example
- [x] P0-01b Zone boundary enforcement (import-linter + ESLint) — violating fixtures fail the check
- [x] P0-02 Project docs and specification copies
- [x] P0-03 Dev compose file (Postgres, Redis, MinIO, Mailpit)
- [x] P0-04 FastAPI app factory, settings, health, errors, request ids
- [x] P0-04b System info and capabilities endpoints
- [x] P0-05 Async SQLAlchemy, Alembic (core + sample branches), model mixins
- [x] P0-06 Module registry and sample module
- [x] P0-07 Auth skeleton (Argon2id, access + rotating refresh)
- [x] P0-08 RBAC skeleton, require(), navigation
- [x] P0-09 Three-gate module gating
- [x] P0-10 Audit hash chain, outbox, tamper detection, append-only guard
- [x] P0-11 Events outbox, Celery worker, jobs table
- [x] P0-12 Action registry and AI tool listing
- [x] P0-13 i18n layered translations with ETag
- [x] P0-14 Theme tokens and active theme endpoint
- [x] P0-15 Controller API: enrollment, licenses, heartbeat, audit ingest
- [x] P0-16 Instance ↔ controller link
- [x] P0-16b Signed school directory
- [x] P0-17 Controller support sessions
- [x] P0-18 Shared frontend packages (generated api-client, tokens, i18n, module-sdk, calendar/money stubs)
- [x] P0-19 School web shell (login, navigation, en/am, light/dark, dashboard, sample page)
- [x] P0-20 Controller web (schools, module toggles, support session, vault) — 12 component tests
- [x] P0-21 Single multi-school mobile app (Expo Go) — 21 Jest tests
- [x] P0-22 AI wiring stub and chat panel
- [x] P0-23 PDF spike with Amharic text
- [x] P0-24 CI pipeline (Python, Node, e2e, api-client diff, i18n, boundaries)
- [x] P0-25 Dev launcher and seed (`up`, `seed`, `reset`, `test`, `mobile`, `logs`, `down`)
- [x] P0-26 Playwright smoke e2e (module gate round-trip, support session, `via=controller` in the vault)

### Checkpoint P0
- [x] `./scripts/dev.sh reset && ./scripts/dev.sh test` is green (76 Python tests, 21 mobile, 12 controller-web, 2 school-web, shared TS suites)
- [x] `./e2e/run.sh` passes: controller login → disable `sample` → school menu loses it → re-enable → "Open as school admin" → sample change → vault shows `via=controller`
- [x] Amharic renders in the PDF spike and in the web UI (Ethiopic font bundled)
- [x] Every connection in the architecture diagram (ARCH §4.1) is exercised by backend/controller tests
- [ ] Mobile app verified in Expo Go on a physical phone — **not possible on this host**; `expo-doctor` 20/20, Jest 21/21, web+android `expo export` succeed, and the signed directory record verifies against the embedded dev key
- [x] `docs/PROGRESS.md` and `docs/DECISIONS.md` are current
- [ ] Tag `v0.0-skeleton` (after the P0 commits)

### Phase 0 verification (2026-11-17)

Commands run from the repository root:

| Command | Result |
| --- | --- |
| `uv run pytest` | 76 passed (backend 43, controller 7, shared 17, zone boundaries 9) |
| `uv run ruff check .` / `ruff format --check .` | clean |
| `uv run lint-imports` | 4/4 contracts kept |
| `python3 scripts/check-i18n.py` | 203 keys, 98 referenced, 0 missing |
| `pnpm -r test` | all suites pass (incl. calendar and mobile) |
| `pnpm -r typecheck` / `lint` / `build` | clean; school web and controller web build |
| `./scripts/gen-api.sh` | committed `schema.d.ts` is up to date |
| `./scripts/dev.sh test` | all 8 steps pass |
| `./scripts/dev.sh reset` → logins at 8000/8100/5173/5174 | school + controller logins OK |
| `./e2e/run.sh` | 1 Playwright smoke test passed |

Known host limitations: no Docker daemon (SQLite fallback), no PostgreSQL binary,
no Expo Go device, no `pwsh` for `scripts/dev.ps1`.

## Phase 1 — Foundations

- [x] P1-01 — API conventions
- [x] P1-02 — Soft-delete base
- [x] P1-03 — Settings system
- [x] P1-04 — Auth hardening (lockout, rate limits, password reset by email + SMS stub, session list/revoke, cookie+CSRF, TOTP 2FA per role)
- [x] P1-05 — Full RBAC (scopes, multiple roles, direct grants/denies, delegation with expiry, "cannot grant what you don't hold") and the route × role matrix test
- [x] P1-06 — Default roles seeded and editable (Super Admin, Director, Academic Head, Department Head, Registrar,…
- [x] P1-07 — Roles and users UI (web)
- [x] P1-08 — Module management UI for the Super Admin (Settings → Modules)
- [x] P1-09 — Audit complete
- [x] P1-10 — Activity history UI (school)
- [x] P1-11 — Rollback/restore
- [x] P1-12 — Controller audit vault UI
- [x] P1-13 — Person and name model
- [x] P1-14 — Name form component (web and mobile) with both script fields, a hint to fill both, and no "last name"…
- [x] P1-15 — Ethiopian calendar package (TS) and module (Python)
- [x] P1-16 — Money package and library (ETB, santim)
- [x] P1-17 — Custom fields engine
- [x] P1-18 — Translation Editor
- [x] P1-19 — "Suggest with AI" hook in the editor (calls the action registry
- [x] P1-20 — i18n tooling
- [x] P1-21 — Theme Manager
- [x] P1-22 — Files service
- [x] P1-23 — Notification service
- [x] P1-24 — Instance setup wizard
- [ ] P1-25 — Jobs UI
- [ ] P1-26 — API compatibility guard
- [ ] P1-SEED — Update seed

## Phase 2 — Academic structure, students and admissions

- [ ] P2-01 — Module `academics`
- [ ] P2-02 — Academic years and terms (semester or quarter chosen per school), open/close, EC/GC display
- [ ] P2-03 — Sections (per level per year, homeroom teacher, capacity), subjects, level-subject assignment, subject groups
- [ ] P2-04 — Curriculum profiles
- [ ] P2-05 — Academics UI (web)
- [ ] P2-06 — Module `students`
- [ ] P2-07 — Student ID generator with configurable format, atomic sequence
- [ ] P2-08 — Students UI (web)
- [ ] P2-09 — Module `admissions`
- [ ] P2-10 — Admissions UI and public application page (optional, toggle) with spam protection
- [ ] P2-11 — Promotion and transfer
- [ ] P2-12 — Mobile
- [ ] P2-13 — Events
- [ ] P2-SEED — Seed

## Phase 3 — Staff, HR and attendance

- [ ] P3-01 — Module `staff`
- [ ] P3-02 — Teaching assignments (teacher ↔ subject ↔ section ↔ year) and the scope resolvers `assigned_subjects`,…
- [ ] P3-03 — Leave
- [ ] P3-04 — Staff UI (web) and basic mobile directory
- [ ] P3-05 — Optional payroll sub-module
- [ ] P3-06 — Module `attendance`
- [ ] P3-07 — Attendance UI (web grid) and mobile quick entry with offline outbox
- [ ] P3-08 — Staff attendance, absence events (`attendance.absent_marked`), reports (by student, section, threshold)
- [ ] P3-SEED — Seed

## Phase 4 — Assessment: marks, grade rules, results

- [ ] P4-01 — `assessment/engine.py`
- [ ] P4-02 — Grade rule engine
- [ ] P4-03 — Rank (tie handling options) and promotion rules (min average, max failed subjects, per-subject minimums)
- [ ] P4-04 — Models and migrations for structures, components, assessments, scores, score revisions, term results,…
- [ ] P4-05 — Structure management APIs and actions
- [ ] P4-06 — Assessment and score APIs
- [ ] P4-07 — Workflow APIs
- [ ] P4-08 — Results
- [ ] P4-09 — Events
- [ ] P4-10 — Mark structure UI (academic head/director)
- [ ] P4-11 — Grade rules UI
- [ ] P4-12 — Web mark-entry grid
- [ ] P4-13 — Mobile mark entry
- [ ] P4-14 — Manager dashboard
- [ ] P4-15 — Approvals UI (department/academic head)
- [ ] P4-16 — Parent and student read views of published results only (web and mobile)
- [ ] P4-17 — Register assessment actions (`assessment.enter_marks`, `assessment.publish`, …) with previews so the AI…
- [ ] P4-SEED — Seed

## Phase 5 — Document Studio

- [ ] P5-01 — Layout JSON schema (elements, positions in mm, styles, bindings, conditions, repeating tables), versioned,…
- [ ] P5-02 — Fields registry
- [ ] P5-03 — Renderer
- [ ] P5-04 — Template models
- [ ] P5-05 — Canvas editor (web)
- [ ] P5-06 — Repeating tables (subjects × components/terms) with totals, average, rank, attendance, remarks
- [ ] P5-07 — Preview with sample or real data (choose a student) before publishing, using the same renderer as production
- [ ] P5-08 — Generation
- [ ] P5-09 — Public verification page `/verify/{code}` showing only minimal data, rate-limited
- [ ] P5-10 — Permissions and workflow
- [ ] P5-11 — Wire existing modules
- [ ] P5-12 — Mobile
- [ ] P5-SEED — Seed

## Phase 6 — Timetable

- [ ] P6-01 — Models
- [ ] P6-02 — Solver in isolation
- [ ] P6-03 — Background generation job with time limit and progress, versioned drafts, failure explanations in plain…
- [ ] P6-04 — Timetable UI
- [ ] P6-05 — Substitute-teacher flow tied to staff leave/absence
- [ ] P6-06 — Outputs
- [ ] P6-07 — Switch attendance to per-period mode when configured
- [ ] P6-SEED — Seed

## Phase 7 — Fees and payments

- [ ] P7-01 — `shared/py/payments.py`
- [ ] P7-02 — Fee models
- [ ] P7-03 — Invoice generation (single, bulk by section/level), numbering, lines, status machine, credits
- [ ] P7-04 — Payments, allocations (one payment → several invoices), receipts (numbered
- [ ] P7-05 — Manual bank adapter
- [ ] P7-06 — Gateway adapters as disabled stubs with sandbox-ready code for Chapa, ArifPay, SantimPay, telebirr and CBE…
- [ ] P7-06b — Multi-provider support
- [ ] P7-07 — Arrears dashboard, reminder automation hooks (`invoice.overdue`), accountant reports (collections,…
- [ ] P7-08 — Fees UI (web) for accountant
- [ ] P7-09 — ETB shown everywhere via the money layer
- [ ] P7-SEED — Seed

## Phase 8 — Communication and portals

- [ ] P8-01 — Announcements
- [ ] P8-02 — Parent–teacher messaging with configurable moderation, per-thread permissions, no cross-family leakage
- [ ] P8-03 — Notification templates UI, channel preferences per user, delivery logs, SMS and push adapters wired (SMS…
- [ ] P8-04 — Parent portal (web + mobile)
- [ ] P8-05 — Student portal with the appropriate subset
- [ ] P8-06 — Push notifications on mobile through the controller push relay
- [ ] P8-SEED — Seed

## Phase 9 — AI layer

- [ ] P9-01 — `core/ai`
- [ ] P9-02 — AI settings
- [ ] P9-03 — Complete the action registry coverage
- [ ] P9-04 — Orchestrator
- [ ] P9-05 — Prompt-injection defenses
- [ ] P9-06 — Chat UI (web and mobile)
- [ ] P9-07 — Voice input
- [ ] P9-08 — Natural-language reports via parameterized report actions (attendance below X, students with arrears,…
- [ ] P9-09 — Content translation
- [ ] P9-10 — Name transliteration suggestion (needs human confirmation), report-card comment drafts, at-risk student…
- [ ] P9-11 — AI usage and cost view, rate limits, audit of AI sessions
- [ ] P9-SEED — Seed

## Phase 10 — Automation engine

- [ ] P10-01 — Rule model (trigger, JSON-logic conditions, action list, optional delay, schedule triggers), validation…
- [ ] P10-02 — Engine
- [ ] P10-03 — Dry-run mode showing what would happen without executing
- [ ] P10-04 — Rule builder UI
- [ ] P10-05 — Starter rules shipped disabled
- [ ] P10-SEED — Seed

## Phase 11 — Control Plane completion

- [ ] P11-01 — CP users and roles (Owner, Support, Billing, Read-only), mandatory 2FA, audit of CP actions
- [ ] P11-02 — Plans and subscriptions
- [ ] P11-03 — Provisioning
- [ ] P11-04 — Instance size profiles (`small|standard|large`) applied at provisioning
- [ ] P11-05 — Monitoring dashboard
- [ ] P11-06 — Audit vault oversight
- [ ] P11-07 — Support sessions hardened
- [ ] P11-08 — Version management
- [ ] P11-09 — Your business revenue in ETB
- [ ] P11-10 — Central push of translations (central layer), themes, and Document Studio templates to selected or all…
- [ ] P11-11 — Backups visibility and restore tooling documented and tested (see Phase 14)
- [ ] P11-12 — Push relay
- [ ] P11-13 — Directory hardening
- [ ] P11-SEED — Seed

## Phase 12 — The single multi-school mobile app: completion and hardening

- [ ] P12-01 — Audit every mobile screen against the web feature list for roles that use mobile (teacher, staff, parent,…
- [ ] P12-02 — Outbox hardening
- [ ] P12-03 — Offline test suite
- [ ] P12-04 — Push notifications end to end, deep linking, notification preferences
- [ ] P12-05 — Mobile performance and UX pass
- [ ] P12-06 — EAS build profiles (development, preview, production), app config, icons, splash, versioning, OTA update…
- [ ] P12-07 — Multi-school accounts
- [ ] P12-08 — Version handshake
- [ ] P12-09 — Release of the single app
- [ ] P12-10 — White-label hook (do not build the feature)
- [ ] P12-SEED — Make sure demo data exercises mobile flows

## Phase 13 — Add-on modules

- [ ] P13-00 — Create the module conformance test (checks manifest completeness, permissions declared, actions have risk…
- [ ] P13-01 — Library (catalog, borrowing, fines in ETB)
- [ ] P13-02 — Transport (routes, stops, vehicles, student assignment, fees link)
- [ ] P13-03 — Inventory
- [ ] P13-04 — Hostel
- [ ] P13-05 — Health clinic (strict permissions, read-audit)
- [ ] P13-06 — Events

## Phase 14 — Hardening and production readiness

- [ ] P14-01 — Security review against ASVS L2 checklist
- [ ] P14-02 — IDOR test sweep
- [ ] P14-03 — Secrets handling review
- [ ] P14-04 — Dependency and container vulnerability scanning in CI
- [ ] P14-05 — Data protection
- [ ] P14-06 — Load tests (k6/Locust) at the large-school scale
- [ ] P14-07 — Database review
- [ ] P14-08 — Failure tests
- [ ] P14-09 — Backups
- [ ] P14-10 — Production compose files (`deploy/compose/instance.yml`, `controller.yml`), Caddy with automatic TLS,…
- [ ] P14-11 — Observability
- [ ] P14-12 — Runbooks in `docs/runbooks`
- [ ] P14-13 — Accessibility and i18n pass
- [ ] P14-14 — Documentation

## Phase 15 — Final dev launcher, seed and release

- [ ] P15-01 — Consolidate `scripts/dev.sh` and `dev.ps1`
- [ ] P15-02 — Final seed
- [ ] P15-03 — `README.md` and `docs/OWNER_TEST_GUIDE.md`
- [ ] P15-04 — Full regression
- [ ] P15-05 — Version tags, changelog, release notes, EAS production build instructions, first-school onboarding…
- [ ] P15-06 — Final review of `docs/DECISIONS.md` and `docs/QUESTIONS.md`
- [ ] P15-07 — Optional

