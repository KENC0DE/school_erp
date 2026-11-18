# Build progress

Follow `docs/02_BUILD_GUIDE.md` in order. Tick a task only when its **Verify**
step passes. Commit format: `P{phase}-{nn}: short description`.

Status markers: `[x]` verified · `[ ]` todo · `[~]` blocked (see
`docs/QUESTIONS.md`).

Last verified: 2026-11-18 (post-reconciliation: `./scripts/dev.sh test` all
steps green, `./e2e/run.sh` smoke + UI gate green; see
`docs/RECONCILIATION.md`).

## Phase 0 — Walking skeleton

- [x] P0-01 Repository, workspaces, tooling, env example
- [x] P0-01b Zone boundary enforcement (import-linter + ESLint) — violating fixture fails
- [x] P0-02 Project docs and specification copies (v1 archived under `docs/archive/v1`)
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
- [x] P0-16b Signed school directory (school code `DEMO`)
- [x] P0-17 Controller support sessions
- [x] P0-18 Shared frontend packages (generated api-client, tokens, i18n, module-sdk, calendar/money stubs)
- [x] P0-19 School web shell (login, navigation, en/am, light/dark, dashboard, sample page)
- [x] P0-19b **Web design foundation** — tokens, fonts, `shared/ts/ui-web` kit, reference screens, UI checklist, token lint
- [x] P0-20 Controller web (schools, module toggles, support session, vault) — 13 component tests
- [x] P0-21 Single multi-school mobile app (Expo Go) — 27 Jest tests
- [x] P0-21b **Mobile design foundation** — native kit from shared tokens, reference screens, screenshots
- [x] P0-22 AI wiring stub and chat panel
- [x] P0-23 PDF spike with Amharic text
- [x] P0-24 CI pipeline (Python, Node, e2e, api-client diff, i18n, boundaries, API compat)
- [x] P0-25 Dev launcher and seed (`up`, `seed`, `reset`, `test`, `mobile`, `logs`, `down`)
- [x] P0-26 Playwright smoke e2e (module gate, banner, support session, `via=controller`) — 3 tests

### Checkpoint P0
- [x] `./scripts/dev.sh reset && ./scripts/dev.sh test` is green (252 backend, 10 controller, 45 shared/zone, 61 school web, 13 controller web, 27 mobile, shared TS)
- [x] Smoke e2e passes (3/3)
- [x] Amharic renders in the PDF spike and in the web UI
- [x] Design foundation (P0-19b, P0-21b) self-reviewed against `docs/UI_CHECKLIST.md` with screenshots
- [x] Every connection in the architecture diagram (ARCH §4.1) is exercised by a test
- [x] `docs/PROGRESS.md` and `docs/DECISIONS.md` current at the end of P0
- [x] Tag `v0.0-skeleton` (pre-reconciliation)

## Phase 1 — Foundations

- [x] P1-01 — API conventions
- [x] P1-02 — Soft-delete base
- [x] P1-03 — Settings system
- [x] P1-04 — Auth hardening
- [x] P1-05 — Full RBAC and route × role matrix test
- [x] P1-06 — Default roles seeded and editable
- [x] P1-07 — Roles and users UI (web)
- [x] P1-08 — Module management UI
- [x] P1-09 — Audit complete
- [x] P1-10 — Activity history UI (school)
- [x] P1-11 — Rollback/restore
- [x] P1-12 — Controller audit vault UI
- [x] P1-13 — Person and name model
- [x] P1-14 — Name form component (web and mobile)
- [x] P1-15 — Ethiopian calendar package and module
- [x] P1-16 — Money package and library (ETB, santim)
- [x] P1-17 — Custom fields engine
- [x] P1-18 — Translation Editor
- [x] P1-19 — "Suggest with AI" hook in the editor
- [x] P1-20 — i18n tooling
- [x] P1-21 — Theme Manager
- [x] P1-22 — Files service
- [x] P1-23 — Notification service (push through the controller relay, stub until P11-12)
- [x] P1-24 — Instance setup wizard
- [x] P1-25 — Jobs UI
- [x] P1-26 — API compatibility guard (95 released paths, CI + test)
- [x] P1-27 **UI quality gate automation** — screenshots, axe, states check, theme layout check
- [x] P1-SEED — Update seed

### Checkpoint P1
- [x] All tests green; permission matrix covers every route × seeded role
- [x] Owner script verified against a fresh seed
- [x] Tag `v0.1-foundations` (re-tag after P0-19b/P0-21b/P1-27)

## Phase 2 — Academic structure, students and admissions

- [x] P2-01 — Module `academics`: levels, stages, school scope
- [x] P2-02 — Academic years and terms
- [x] P2-03 — Sections, subjects, level-subject assignment, groups
- [x] P2-04 — Curriculum profiles
- [x] P2-05 — Academics UI (web)
- [x] P2-06 — Module `students`
- [x] P2-07 — Student ID generator with configurable format, atomic sequence
- [x] P2-08 — Students UI (web)
- [x] P2-09 — Module `admissions`
- [x] P2-10 — Admissions UI and public application page
- [x] P2-11 — Promotion and transfer
- [x] P2-12 — Mobile: student directory/profile/registration
- [x] P2-13 — Events
- [x] P2-SEED — Seed

## Phase 3 — Staff, HR and attendance

- [x] P3-01 — Module `staff`
- [x] P3-02 — Teaching assignments and scope resolvers
- [x] P3-03 — Leave
- [x] P3-04 — Staff UI and basic mobile directory
- [ ] P3-05 — Optional payroll sub-module
- [ ] P3-06 — Module `attendance`
- [ ] P3-07 — Attendance UI and mobile offline entry
- [ ] P3-08 — Staff attendance, events, reports
- [ ] P3-SEED — Seed

## Phase 4 — Assessment: marks, grade rules, results

- [x] P4-01 — `assessment/engine.py`
- [x] P4-02 — Grade rule engine
- [x] P4-03 — Rank and promotion rules
- [ ] P4-04 — Models and migrations
- [ ] P4-05 — Structure management APIs and actions
- [ ] P4-06 — Assessment and score APIs
- [ ] P4-07 — Workflow APIs
- [ ] P4-08 — Results
- [ ] P4-09 — Events
- [ ] P4-10 — Mark structure UI
- [ ] P4-11 — Grade rules UI
- [ ] P4-12 — Web mark-entry grid
- [ ] P4-13 — Mobile mark entry
- [ ] P4-14 — Manager dashboard
- [ ] P4-15 — Approvals UI
- [ ] P4-16 — Parent and student read views
- [ ] P4-17 — Assessment actions and document fields
- [ ] P4-SEED — Seed

## Phase 5 — Document Studio

- [ ] P5-01 — Layout JSON schema
- [ ] P5-02 — Fields registry
- [ ] P5-03 — Renderer
- [ ] P5-04 — Template models
- [ ] P5-05 — Canvas editor (web)
- [ ] P5-06 — Repeating tables
- [ ] P5-07 — Preview with sample or real data
- [ ] P5-08 — Generation
- [ ] P5-09 — Public verification page
- [ ] P5-10 — Permissions and workflow
- [ ] P5-11 — Wire existing modules
- [ ] P5-12 — Mobile view/share/print
- [ ] P5-SEED — Seed

## Phase 6 — Timetable

- [ ] P6-01 — Models
- [ ] P6-02 — Solver in isolation
- [ ] P6-03 — Background generation job
- [ ] P6-04 — Timetable UI
- [ ] P6-05 — Substitute-teacher flow
- [ ] P6-06 — Outputs
- [ ] P6-07 — Per-period attendance
- [ ] P6-SEED — Seed

## Phase 7 — Fees and payments

- [ ] P7-01 — `shared/py/payments.py`
- [ ] P7-02 — Fee models
- [ ] P7-03 — Invoice generation
- [ ] P7-04 — Payments, allocations, receipts, refunds
- [ ] P7-05 — Manual bank and cash adapters
- [ ] P7-06 — Gateway adapters as disabled stubs
- [ ] P7-06b — Multi-provider support
- [ ] P7-07 — Arrears, reminders, accountant reports
- [ ] P7-08 — Fees UI and parent pay flow
- [ ] P7-09 — ETB through the money layer
- [ ] P7-SEED — Seed

## Phase 8 — Communication and portals

- [ ] P8-01 — Announcements
- [ ] P8-02 — Parent–teacher messaging
- [ ] P8-03 — Notification templates UI and adapters
- [ ] P8-04 — Parent portal (web + mobile)
- [ ] P8-05 — Student portal
- [ ] P8-06 — Push notifications on mobile through the controller relay
- [ ] P8-SEED — Seed

## Phase 9 — AI layer

- [ ] P9-01 — `core/ai` providers
- [ ] P9-02 — AI settings
- [ ] P9-03 — Complete action registry coverage
- [ ] P9-04 — Orchestrator
- [ ] P9-05 — Prompt-injection defenses
- [ ] P9-06 — Chat UI (web and mobile)
- [ ] P9-07 — Voice input
- [ ] P9-08 — Natural-language reports
- [ ] P9-09 — Content translation
- [ ] P9-10 — Transliteration, comments, at-risk alerts
- [ ] P9-11 — AI usage and cost view
- [ ] P9-SEED — Seed

## Phase 10 — Automation engine

- [ ] P10-01 — Rule model
- [ ] P10-02 — Engine
- [ ] P10-03 — Dry-run mode
- [ ] P10-04 — Rule builder UI
- [ ] P10-05 — Starter rules
- [ ] P10-SEED — Seed

## Phase 11 — Control Plane completion

- [ ] P11-01 — CP users and roles, 2FA, audit
- [ ] P11-02 — Plans and subscriptions
- [ ] P11-03 — Provisioning
- [ ] P11-04 — Instance size profiles
- [ ] P11-05 — Monitoring dashboard
- [ ] P11-06 — Audit vault oversight
- [ ] P11-07 — Support sessions hardened
- [ ] P11-08 — Version management
- [ ] P11-09 — Revenue in ETB
- [ ] P11-10 — Central push of translations/themes/templates
- [ ] P11-11 — Backups visibility and restore tooling
- [ ] P11-12 — Push relay
- [ ] P11-13 — Directory hardening
- [ ] P11-SEED — Seed

## Phase 12 — The single multi-school mobile app: completion and hardening

- [ ] P12-01 — Audit mobile screens against web
- [ ] P12-02 — Outbox hardening
- [ ] P12-03 — Offline test suite
- [ ] P12-04 — Push notifications end to end
- [ ] P12-05 — Mobile performance and UX pass
- [ ] P12-06 — EAS build profiles
- [ ] P12-07 — Multi-school accounts
- [ ] P12-08 — Version handshake
- [ ] P12-09 — Release of the single app
- [ ] P12-10 — White-label hook (document only)
- [ ] P12-SEED — Demo data exercises mobile flows

## Phase 13 — Add-on modules (only from `docs/OWNER_REQUESTS.md`)

- [ ] P13-00 — Module conformance test
- [ ] P13-01 — Library
- [ ] P13-02 — Transport
- [ ] P13-03 — Inventory
- [ ] P13-04 — Hostel
- [ ] P13-05 — Health clinic
- [ ] P13-06 — Events

## Phase 14 — Hardening and production readiness

- [ ] P14-01 — Security review (ASVS L2)
- [ ] P14-02 — IDOR sweep
- [ ] P14-03 — Secrets handling review
- [ ] P14-04 — Dependency and container scanning
- [ ] P14-05 — Data protection
- [ ] P14-06 — Load tests
- [ ] P14-07 — Database review
- [ ] P14-08 — Failure tests
- [ ] P14-09 — Backups and restore drill
- [ ] P14-10 — Production compose and Caddy
- [ ] P14-11 — Observability
- [ ] P14-12 — Runbooks
- [ ] P14-13 — Full visual review against `docs/UI_CHECKLIST.md` + accessibility/i18n pass
- [ ] P14-14 — Documentation

## Phase 15 — Final dev launcher, seed and release

- [ ] P15-01 — Consolidate dev scripts and add `smoke`
- [ ] P15-02 — Final seed
- [ ] P15-03 — README and owner test guide
- [ ] P15-04 — Full regression
- [ ] P15-05 — Tags, changelog, release notes, onboarding checklist
- [ ] P15-06 — Final review of decisions and questions
- [ ] P15-07 — Optional repo split rehearsal (document only)
