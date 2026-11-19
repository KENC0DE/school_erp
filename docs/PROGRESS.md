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
- [x] P3-05 — Optional payroll sub-module
- [x] P3-06 — Module `attendance`
- [x] P3-07 — Attendance UI and mobile offline entry
- [x] P3-08 — Staff attendance, events, reports
- [x] P3-SEED — Seed

### Checkpoint P3
- [x] All tests green, including the mobile offline outbox sync test and the attendance scope-isolation tests.
- [x] UI quality gate and Playwright e2e green on a fresh seed.
- [ ] Owner script on a physical phone (log in as each teacher, mark attendance with airplane mode on, reconnect and sync) — **not possible on this host**; see `docs/QUESTIONS.md` item 9.
- [x] Tag `v0.3-staff-attendance`.

### Phase 3 verification (2026-11-18)

| Command | Result |
| --- | --- |
| `uv run pytest school-erp/backend/tests` | 381 passed |
| `pnpm -r --if-present typecheck` | all 11 workspace projects clean |
| `pnpm -r --if-present test` | 205 passed (school 88, controller 13, mobile 62, shared 42) |
| `pnpm -r --if-present build` | school and controller production builds OK |
| `./e2e/run.sh` | 8 passed, 6 opt-in screenshot captures skipped; axe/UI gate and smoke green |
| `ruff check` / `check-i18n` / `lint-imports` / `check-api-compat` | clean |

## Phase 4 — Assessment: marks, grade rules, results

- [x] P4-01 — `assessment/engine.py`
- [x] P4-02 — Grade rule engine
- [x] P4-03 — Rank and promotion rules
- [x] P4-04 — Models and migrations (marks as integer micro-units, partial live indexes)
- [x] P4-05 — Structure management APIs and actions (impact preview, recalculation job)
- [x] P4-06 — Assessment and score APIs
- [x] P4-07 — Workflow APIs
- [x] P4-08 — Results
- [x] P4-09 — Events
- [x] P4-10 — Mark structure UI
- [x] P4-11 — Grade rules UI
- [x] P4-12 — Web mark-entry grid
- [x] P4-13 — Mobile mark entry
- [x] P4-14 — Manager dashboard
- [x] P4-15 — Approvals UI
- [x] P4-16 — Parent and student read views
- [x] P4-17 — Assessment actions and document fields
- [x] P4-SEED — Seed

### Checkpoint P4
- [x] Engine tests exhaustive and green; conversion-bound and recalculation-idempotency property tests.
- [x] Owner script: academic head defines components and bands, teacher enters 15- and 13-mark assessments, submit → approve → publish, band change relabels without touching raw marks, correction after lock, parent sees only published results (automated in `tests/test_owner_script_assessment.py`).
- [x] Performance recorded in `docs/DECISIONS.md` (60-student entry 0.17 s, 3,000-student recalculation 1.2 s).
- [x] Tag `v0.4-assessment`.

### Phase 4 verification (2026-11-19)

| Command | Result |
| --- | --- |
| `uv run pytest school-erp/backend/tests` | 425 passed across 61 files in four chunks (137 + 100 + 97 + 91), plus the owner-script test added at the checkpoint (1 passed) |
| `test_owner_script_assessment.py` | 1 passed — full owner script over the API with academic head, teacher and parent accounts |
| `scripts/bench_assessment.py` | 60-student entry 0.17 s; 3,000-student / 15,000-score recalculation 1.2 s |
| `pnpm -r --if-present test` (web + mobile) | web 125 passed (29 files); mobile 86 passed (17 suites) |
| `tsc --noEmit` (web, mobile) | clean |
| `vite build` (school web) | OK |
| `./e2e/run.sh` | 9 passed, 6 opt-in screenshot captures skipped; keyboard mark entry, smoke, axe and UI quality gate green |
| `ruff check` / `ruff format --check` / `check-i18n` / `lint-imports` / `check-api-compat` / `gen-api.sh` | clean (2549 i18n keys, 4 contracts kept, 95 released paths compatible, client up to date) |
| `alembic heads` | `0029_portal_links` |

## Phase 5 — Document Studio

- [x] P5-01 — Layout JSON schema
- [x] P5-02 — Fields registry
- [x] P5-03 — Renderer
- [x] P5-04 — Template models: draft/publish lifecycle, duplicate, JSON import/export, 7 starters (12 tests)
- [x] P5-05 — Canvas editor (web): drag/resize, text, image, shape, line, table, QR/barcode, logo/signature/stamp/photo, field insertion, snap, layers, undo/redo, zoom, page setup (Playwright + 3 editor tests)
- [x] P5-06 — Repeating tables: grouped headers, row totals/averages/ranks, summaries, attendance/remarks, conditional Promoted/Repeat blocks (4 table tests + renderer/schema fixtures)
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

## Phase 16 — Public school website module (starts after the Phase 15 RELEASE CHECKPOINT)

Specification: `docs/03_WEBSITE_MODULE.md` (WEB). Do not start any task here before
the Phase 15 RELEASE CHECKPOINT is complete.

### Foundation
- [ ] P16-01 — Scaffold module `website` (manifest, permissions, i18n, settings, licensable, default off)
- [ ] P16-02 — Move the ERP web app under `/app` (`APP_BASE_PATH`, routing, links, Caddy, e2e)
- [ ] P16-03 — Models and migrations for all WEB §8 tables
- [ ] P16-04 — Public media pipeline (validation, derivatives, placeholders, alt text, consent, SVG policy)
- [ ] P16-05 — Block system (schemas, registry, versioning, validation, minimum block set)
- [ ] P16-06 — SSR renderer (Jinja2, token CSS, progressive JS, cache, ETag)
- [ ] P16-07 — Templates `modern-clean`, `warm-primary`, `academic-classic` (optional `bold-contemporary`)
- [ ] P16-08 — Public routing and i18n (`/`, `/{locale}/…`, hreflang, reserved slugs, error pages)
- [ ] P16-09 — SEO (meta, Open Graph, JSON-LD, sitemap, robots, canonical, noindex for drafts)
- [ ] P16-10 — Rich-text sanitizer and constrained editor component
- [ ] P16-11 — Pages and versions (draft, preview, publish, schedule, rollback, audit, events)
- [ ] P16-12 — News and events (EC/GC display, add-to-calendar, publish from announcement)
- [ ] P16-13 — Public staff profiles, gallery, downloads, FAQ, testimonials with consent gates
- [ ] P16-14 — Forms (inquiry/contact, honeypot, rate limit, CAPTCHA stub, inbox, admissions CTA)
- [ ] P16-15 — Public data bridge (whitelisted minimal fields, privacy leak scan)

### Editor in the ERP
- [ ] P16-16 — Website Manager shell and dashboard
- [ ] P16-17 — Page editor (blocks, add-block gallery, schema forms, live preview, undo/redo, auto-save)
- [ ] P16-18 — Media library UI (upload, crop, alt text, consent, usage)
- [ ] P16-19 — Menus, footer and site settings
- [ ] P16-20 — Template and style picker with non-destructive switching
- [ ] P16-21 — Publish workflow UI (preview, publish, schedule, history, rollback)
- [ ] P16-22 — "Create my site" wizard
- [ ] P16-23 — Domains (default subdomain, custom-domain verification, generated Caddy config)

### AI and controller
- [ ] P16-24 — Register website actions (risk levels, previews, consent enforcement)
- [ ] P16-25 — Controller license key, plan inclusion, heartbeat `site_published`, CP toggle

### Quality
- [ ] P16-26 — Performance budgets and Lighthouse CI
- [ ] P16-27 — Accessibility and i18n pass
- [ ] P16-28 — Security tests (XSS, CSP, uploads, rate limits, leak scan, consent, draft isolation)
- [ ] P16-29 — Visual review and `docs/website/WEBSITE_CHECKLIST.md`
- [ ] P16-30 — Documentation (editor guide, domain runbook)
- [ ] P16-31 — E2E (Playwright) of the full website journey
- [ ] P16-32 — Update README, owner test guide and dev launcher; full regression
- [ ] P16-SEED — Published demo site for Demo Academy (English and Amharic)

### Phase 16 checkpoint
- [ ] All WEB §15 acceptance criteria are true and recorded.
- [ ] The full suite, smoke e2e and Lighthouse CI are green on the seeded demo site.
- [ ] Tag `v1.1.0`, then write `docs/FINAL_REPORT.md` (GUIDE §0.7).
