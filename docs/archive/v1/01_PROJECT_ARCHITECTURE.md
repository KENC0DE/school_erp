# School ERP Platform: Project and Architecture Specification

**Document 1 of 2.** This file describes *what* is being built and *how it is structured*.
Document 2 (`02_BUILD_GUIDE.md`) is the step-by-step checklist the builder AI follows.

> **Rule for the builder AI:** this document is the source of truth. If a build task and this document disagree, follow this document and record the conflict in `docs/DECISIONS.md`. Library APIs change quickly, so verify every library's current official documentation before using it and pin exact versions in lockfiles. Do not rely on memory.

---

## 1. Vision and goals

An **AI-first, highly configurable School ERP for Ethiopian schools**, sold as a subscription. Every school gets its **own isolated instance**. A separate **Control Plane** (the owner's private manager system) provisions, licenses, monitors, audits and supports all instances.

**Goals**
1. **Plug-and-play modularity.** Every feature beyond a small core is a module that can be switched on and off per school without data loss or friction.
2. **Configuration over code.** Curriculum, grade range, term system, mark structure, grade rules, fees, certificates, languages, themes and terminology are all settings, never forks.
3. **AI-first.** Each school can add its own AI provider key, then do almost anything in the system by text or voice, strictly within the logged-in user's permissions.
4. **Ethiopian fit.** Three-part names (given, father's, grandfather's) in Ge'ez and Latin script, the Ethiopian calendar, ETB currency, Amharic UI, local payment channels, unreliable connectivity.
5. **Trust and accountability.** Every change is recorded, tamper-evident, restorable, and visible to the right people.
6. **Automation.** Reduce manual work through rules, background jobs and AI.

**Non-goals for v1:** multi-school shared database (we use one database per school), a public marketplace, native desktop apps (the web app is the desktop experience).

## 2. Glossary

| Term | Meaning |
|---|---|
| **Instance** | One deployed School ERP (API, worker, database, storage) belonging to one school. |
| **Control Plane (CP)** | The owner's manager system. Not an ERP. |
| **Module** | A self-contained feature package with a manifest (backend and frontend). |
| **Three gates** | Licensed (CP) → Enabled (school) → Permitted (role). All three must pass. |
| **Action** | A typed, permission-checked operation registered once and usable by REST, AI, and automation. |
| **Component** | An official part of a term mark (e.g. Mid-exam out of 20). |
| **Assessment** | A single test, quiz or assignment a teacher records, with its own "out of" value. |
| **Santim** | 1/100 ETB. All money is stored as integer santim. |
| **EC / GC** | Ethiopian Calendar / Gregorian Calendar. |

## 3. Personas

| Persona | Lives in | Notes |
|---|---|---|
| **Platform Owner** | CP | Full control, sees everything including technical logs. |
| **Controller Support** | CP | Staff of the owner, with limited CP permissions. |
| **School Super Admin** | Instance | Highest school account. Manages staff and roles. Cannot see technical logs. |
| **Director / Principal** | Instance | Oversees academics, approves results. |
| **Academic Head / Dept Head** | Instance | Defines mark structure, reviews and approves marks. |
| **Registrar** | Instance | Admissions, student records, documents. |
| **Teacher / Homeroom** | Instance | Attendance, marks, communication. Sees own classes only. |
| **Accountant / HR Officer** | Instance | Fees and payments / staff and leave. |
| **Parent / Student** | Instance (portal) | Read mostly: published marks, attendance, fees, announcements. |

The Platform Owner can **open any instance as that school's Super Admin** through a controller session (section 8.6). Every action in such a session is tagged `via=controller`.

---

## 4. System architecture

### 4.1 Topology

```
                ┌──────────────────────── CONTROL PLANE ────────────────────────┐
                │ controller-web (React)  ──►  controller-api (FastAPI)           │
                │   schools, plans, licenses, monitoring, audit vault, support    │
                │   DB: controller_db (Postgres)   signing keys (Ed25519)         │
                └───────▲──────────────┬───────────────────────────┬─────────────┘
          heartbeat,    │ signed       │ signed support session    │ provisioning
          audit batches │ license/cfg  │ (impersonation)           │ (scripts → later agent)
                ┌───────┴──────────────▼───────────────────────────▼─────────────┐
                │                 SCHOOL INSTANCE (one per school)                │
 Browser ─────► │ web (static SPA) ─► api (FastAPI modular monolith) ◄─ worker   │
 Mobile (RN) ─► │                     │         │          │         (Celery)    │
 Parents ─────► │                  Postgres   Redis    S3-compatible storage      │
                └──────────────────────────────────────────────────────────────────┘
                   Several instances may share one host. Each has its own DB and secrets.
```

### 4.2 Key decisions

| Decision | Choice | Why |
|---|---|---|
| Architecture style | **Modular monolith** per instance | One deployable, clean module boundaries, easy for AI to build step by step. No microservices. |
| Tenancy | **Single tenant per instance**, one DB per school | Isolation, easy backup and restore, no tenant-id bugs. |
| Hosting | Docker Compose per instance; several instances can share a host | Flexible per the owner's requirement. Host choice is not baked into code. |
| API | REST + OpenAPI, versioned `/api/v1`; typed clients generated from OpenAPI | One contract for web, mobile and controller. |
| Realtime | SSE/WebSocket only for AI streaming and notifications | Keep everything else plain HTTP. |
| Background work | Celery + Redis (worker and beat) | Bulk PDFs, notifications, recalculations, audit shipping, backups. |
| Repository | **One repo, three zones** (`school-erp/`, `owner/`, `shared/`) with enforced import boundaries | One place for the AI to work, and a mechanical split later if needed (§4.4). |
| Mobile app | **One app for all schools** with a school picker and a controller-hosted school directory | Easier to publish and maintain than one app per school (§8.9). |
| Source of truth for logic | **Service layer + action registry** | REST handlers, AI tools and automation all call the same services. |

### 4.3 Technology stack

> Use the latest stable versions at build time. Verify current APIs in official docs. Pin exact versions.

| Area | Choice |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x (async), Alembic, `uv` for dependency management |
| Database | PostgreSQL (latest stable), UUIDv7 or ULID primary keys, JSONB for flexible fields |
| Cache / queue | Redis, Celery, Celery Beat |
| Object storage | S3-compatible API (MinIO in dev; any S3-compatible service in production) |
| Auth | Argon2id password hashing, short-lived JWT access tokens, rotating refresh tokens, optional TOTP 2FA |
| Web (school and controller) | React + TypeScript + Vite, Tailwind CSS v4, shadcn/ui, TanStack Query, TanStack Table + Virtual, React Hook Form + Zod, i18next/react-i18next |
| Canvas (Document Studio) | A canvas library such as Konva (react-konva) or Fabric.js, with layout saved as our own JSON schema |
| Mobile | React Native with Expo (Expo Router, Expo Go for dev, EAS Build for releases), TanStack Query with persisted cache, expo-sqlite for the offline outbox, expo-secure-store, expo-notifications |
| Timetable solver | Google OR-Tools CP-SAT |
| PDF rendering | HTML → PDF with a headless Chromium (Playwright) as the primary candidate, WeasyPrint as fallback. **Decided by the Amharic rendering spike in task P0-23.** |
| Reverse proxy | Caddy (automatic TLS) |
| Quality | ruff, mypy or pyright, pytest + pytest-asyncio + httpx, factory_boy, Vitest, Testing Library, Playwright (web e2e), Maestro (optional mobile e2e), GitHub Actions |
| Monorepo | pnpm workspaces for JS, `uv` workspace for Python |

### 4.4 Repository layout and boundaries

**One repository, three zones.** AI-driven builds are most reliable when a change can be made in one place, so everything lives in one repo. The zones keep a clean seam, so the repo can be split later without rework.

```
erp-platform/
├─ school-erp/                    # ZONE 1: what is deployed to every school
│  ├─ backend/                    # School ERP API (FastAPI)
│  │   ├─ app/                    # app factory, settings, wiring
│  │   ├─ core/                   # shared kernel: auth rbac audit config db events jobs
│  │   │                          #   i18n themes files notify names calendar money actions licensing ai
│  │   ├─ modules/<key>/          # one package per module (see §4.5)
│  │   ├─ alembic/                # migrations env (branch per module)
│  │   └─ tests/
│  └─ web/                        # School web app (React): the desktop experience
├─ owner/                         # ZONE 2: what only the owner runs and publishes
│  ├─ controller-api/             # Control Plane API (FastAPI)
│  ├─ controller-web/             # Control Plane UI (React)
│  └─ mobile/                     # THE single Expo app for ALL schools (see §8.9)
│      └─ src/{modules/<key>/, ui/, schools/, sync/}   # module screens, native UI kit, school picker, outbox
├─ shared/                        # ZONE 3: contracts and common code only
│  ├─ py/                         # protocol schemas, license sign/verify, payments adapter interface, money
│  └─ ts/                         # api-client (generated), tokens, i18n runtime loader,
│                                 #   calendar, money, module-sdk, ui-web (shadcn-based components)
├─ deploy/                        # compose, caddy, backups, provisioning
├─ scripts/                       # dev.sh, dev.ps1, seed, e2e
└─ docs/                          # specs, PROGRESS.md, DECISIONS.md, QUESTIONS.md, runbooks
```

**Boundary rules (enforced automatically in CI and pre-commit):**
1. `school-erp/` never imports anything from `owner/`.
2. `owner/` may import from `shared/`. It talks to school servers **only through the HTTP API**, using the generated `api-client`. It never imports `school-erp` code.
3. `shared/` imports nothing from the other zones and contains only contracts and pure utilities.
4. A feature that reaches mobile spans two zones (`school-erp/backend` and `owner/mobile`). That is an accepted cost: it is still one repo and one change.
5. Enforcement: Python `import-linter` contracts, TypeScript restricted-import rules (ESLint or dependency-cruiser), and a test with a deliberately violating fixture that must fail.

**Why the mobile app sits in `owner/`:** the owner holds the app-store accounts, the signing keys and the app's trust anchor (the controller's public key), so the app is built and published by the owner, not per school. It still shares most code with the school web app through `shared/`.

**Splitting later:** because of the rules above, a split is mechanical: `shared/` becomes versioned private packages, the school API's OpenAPI schema becomes a published contract artifact, and each side gets its own CI. A rehearsal task (P15-07) documents the procedure. Do not split until there is a real reason (outside developers who should not see the controller, or selling the school ERP separately).

### 4.5 Module system

A module is a folder `school-erp/backend/modules/<key>/` with a manifest, plus matching frontend modules in `school-erp/web` and `owner/mobile/src/modules/<key>/` (registered through `shared/ts/module-sdk`).

```
modules/<key>/
  manifest.py      # declares everything the module contributes
  models.py        # SQLAlchemy models
  schemas.py       # Pydantic models
  service.py       # business logic (only place that mutates data)
  router.py        # REST endpoints; each declares a permission
  actions.py       # registered Actions (REST/AI/automation share these)
  events.py        # domain events emitted and handled
  fields.py        # document fields offered to Document Studio
  migrations/      # Alembic revisions with branch label = <key>
  i18n/en.json  i18n/am.json     # default strings for namespace <key>
  tests/
```

**Backend manifest (illustrative):**

```python
MANIFEST = ModuleManifest(
    key="assessment",
    name="Marks & Grading",
    version="1.0.0",
    depends_on=["academics", "students", "staff"],
    permissions=[Perm("assessment.marks.enter", scopes=["assigned_subjects"]), ...],
    router=router,
    actions=ACTIONS,
    events=EVENTS,
    i18n_namespaces=["assessment"],
    document_fields=FIELDS,
    settings_schema=AssessmentSettings,
    nav=[Nav(key="marks", label_key="assessment.nav.marks", perm="assessment.marks.enter", path="/marks")],
    licensable=True,
    default_enabled=False,
    core=False,
)
```

**Rules**
- The loader scans `modules/*/manifest.py`, validates dependencies (no cycles), and mounts routers at `/api/v1/<key>`.
- **All migrations are applied to every instance.** A module being off means its routes and UI are gated, but its tables exist. This is what makes switching on and off frictionless and lossless.
- Alembic uses one **branch label per module** plus a `core` branch. Use `alembic upgrade heads`.
- Modules may depend on other modules' **services and events**, never on their tables directly. Cross-module reads go through service functions.
- Cross-module reactions go through the **event bus**, not direct calls, whenever the dependency is optional.
- Frontend manifests register routes, nav items, permission requirements and mobile screens. The shell builds navigation from the registry.

**The three gates** are enforced in one place (`core/licensing` and `core/rbac`):
1. **Licensed:** the signed license from the CP lists the module. Verified offline with the CP public key, with a configurable grace period when the CP is unreachable.
2. **Enabled:** the school Super Admin toggles it in Settings → Modules (stored in `instance_modules`). Turning off checks for dependants and warns. Turning on a module whose dependency is off is blocked with a clear message.
3. **Permitted:** the user's role has the module's permission. The menu, the API and the AI tool list all derive from the same check.

Disabled-module API calls return `403 MODULE_DISABLED`. Toggles are applied immediately (cache invalidated), need no redeploy, and are audited.

**Core (always on, not licensable):** auth, users, roles and permissions, audit, settings, modules registry, i18n, themes, files, notifications, persons and names, custom fields, instance setup.

**Licensable modules:** academics, students, admissions, staff, attendance, assessment (marks and grading), timetable, fees, documents (Document Studio), communication, portals, ai (assistant), automation, plus add-ons (library, transport, inventory, hostel, health, events).

---
## 5. Cross-cutting design (shared kernel)

### 5.1 Conventions

- **API:** `/api/v1/...`, JSON, `snake_case` fields. Cursor or page-based pagination (`limit`, `cursor`) with a consistent envelope `{items, next_cursor, total?}`. Filtering and sorting through explicit query parameters.
- **Errors:** one format `{error: {code, message_key, message, details, request_id}}`. Codes are stable strings (`MODULE_DISABLED`, `PERMISSION_DENIED`, `VALIDATION_ERROR`, `CONFLICT`, ...). `message_key` is an i18n key so errors are translatable.
- **IDs:** UUIDv7/ULID. **Timestamps:** UTC in DB, `Africa/Addis_Ababa` for display.
- **Concurrency:** every mutable row has `row_version`. Updates send the expected version. A mismatch returns `409 CONFLICT` with the current state.
- **Idempotency:** mutating endpoints accept an `Idempotency-Key` header (required for the mobile outbox and payment webhooks). Results are stored for 24 hours.
- **Soft delete:** every business table has `deleted_at`, `deleted_by`. Hard deletes are forbidden except for expired temporary data. Default queries exclude deleted rows.
- **Layering:** `router → service → repository/models`. Routers never touch the DB directly. Services are the only mutators and always write audit entries.
- **Never** use floating point for money or marks. Use `Decimal` (Python) and integer santim or fixed-scale decimals in the DB.

### 5.2 Authentication and sessions

- Login by email or phone plus password. Argon2id. Lockout and rate limiting on failed attempts.
- Access token (≈15 minutes) plus rotating refresh token. Web: httpOnly secure cookies with CSRF protection. Mobile: tokens in `expo-secure-store`.
- Optional TOTP 2FA, enforceable per role by the Super Admin.
- Mobile keeps **one session per school** (§8.9), stored separately in secure storage.
- Session list with remote revoke. Password reset via email or SMS code.
- **Controller sessions** are a separate actor type (section 8.6).

### 5.3 Roles and permissions (RBAC)

- Permission codes: `module.resource.action`, such as `students.record.view`, `assessment.marks.approve`.
- **Scopes** narrow a permission: `all`, `own_class`, `assigned_subjects`, `department`, `own_children`, `self`. A role grants `(permission, scope)` pairs.
- Users can have several roles. Optional direct grants and explicit denies. **Temporary delegation** with an expiry.
- Custom roles per school. Default roles are seeded and editable: Super Admin, Director, Academic Head, Department Head, Registrar, Teacher, Homeroom Teacher, Accountant, HR Officer, Librarian, Parent, Student.
- A single dependency `require("perm.code", scope_resolver)` guards each endpoint. **A CI test fails if any route lacks a permission declaration** (or an explicit `public` marker).
- The effective permission set is computed once per request, cached briefly, and shared by the API guard, the menu builder (`GET /me/navigation`) and the AI tool filter.
- Only roles that hold `roles.manage` can grant permissions, and nobody can grant a permission they do not hold themselves.

### 5.4 Audit and history

**Three visibility tiers**

| Tier | Content | Who sees it |
|---|---|---|
| **A. Activity history** | Business actions: who created, changed, deleted or approved what, with before/after values | School users with `audit.activity.view` (assigned by the Super Admin in settings), filtered by module and scope. The Super Admin holds it by default. |
| **B. Technical and security logs** | Errors, stack traces, system jobs, login anomalies, infrastructure events | **Controller only** |
| **C. Immutable vault** | Full tamper-evident copy of all audit entries | **Controller only** |

Default decision: actions performed by the Super Admin themselves are hidden from Tier A unless a role holds `audit.activity.view_admin_actions` (not granted by default). Controller sessions are always labeled.

**Audit entry fields:** `seq, ts, actor_type (user|ai|controller|automation|system), actor_id, on_behalf_of, via (web|mobile|api|ai|controller|automation), ip, user_agent, module, entity_type, entity_id, action, before, after, reason, request_id, reverts_id, prev_hash, hash`.

**Tamper evidence:** `hash = SHA256(prev_hash ‖ canonical_json(entry))`, a per-instance chain. The app's database role has **no UPDATE or DELETE rights** on the audit table. Entries are shipped to the CP in order with sequence numbers. The CP stores the chain head, so any local alteration or deletion is detectable. A `verify_chain` job runs nightly.

**Rollback:** entity types opt in by implementing a `Revertible` protocol. A rollback is a new audited change (`reverts_id` points to the original), never an erasure. Restoring a soft-deleted record works the same way. Reverting requires a dedicated permission and a reason.

**Read auditing:** sensitive reads (medical records, full student export) are logged as audit entries of type `read`.

### 5.5 Events, jobs, notifications

- **Domain events** (`student.admitted`, `attendance.absent_marked`, `marks.published`, `invoice.overdue`, `term.closed`, ...) go through an outbox table, so they are never lost, and are then dispatched to handlers and the automation engine.
- **Jobs** (Celery): bulk document generation, recalculation, notification delivery, audit shipping, heartbeats, backups, nightly integrity checks. Every long job has a status record (`jobs` table) visible in the UI, with progress and retry.
- **Notification channels** through adapters: in-app, push (Expo), email (SMTP), SMS (provider adapter, credentials supplied later), Telegram (optional). Templates have variables and are translatable. Delivery logs are kept.

### 5.6 Internationalization (no hard-coded text)

- **Engine:** i18next / react-i18next on web and mobile. Keys, namespaces per module, ICU-style plurals. No user-facing string is ever written inline in code.
- **Runtime-editable storage:** `translation_entries(namespace, key, locale, value, status, source, layer, updated_by)`.
- **Three layers, most specific wins:** `default` (shipped in module files) < `central` (pushed from the CP to all schools) < `school` (the school's own overrides, including terminology such as "Grade" vs "Class").
- **Delivery:** `GET /api/v1/i18n/{locale}/{namespace}` returns the merged result with an ETag. Apps cache it and refresh on change, so edits show up without redeploying and the mobile app updates over the air.
- **Translation Editor** (Settings → Languages): table of key, English source and target text. Search, filter by module, filter by missing or needs review. Import/export CSV and JSON. **"Suggest with AI"** creates drafts marked `needs_review`, never auto-approved. In-context editing mode (click text on screen to edit its translation).
- **Locales:** `en` (default fallback) and `am` in phase one. `om` (Afan Oromo, Latin script) and `ti` (Tigrinya, Ge'ez script) are added later by adding translation entries. Locale metadata (script, direction, font) lives in a `locales` table.
- **Fonts:** an Ethiopic font (Noto Sans Ethiopic or similar open font) is bundled for web, mobile and PDFs. Layouts must tolerate longer text.
- **Content translations** (not UI): `content_translations(entity_type, entity_id, field, locale, value, source[ai|human], status, reviewed_by, reviewed_at)`. Used for free-text fields only: announcements, report-card comments, messages, notes, template wording. Saved only when the user clicks Save. The original is never overwritten.
- **Names are never machine-translated.** The AI may suggest a transliteration which a human confirms (section 5.8).
- Dates, numbers and currency go through the formatting layer (section 5.7 and 5.9) according to the active locale and the school's calendar preference.

### 5.7 Ethiopian calendar and dates

- **Storage:** dates are always stored as Gregorian ISO dates. The Ethiopian calendar is a **display and input layer only**.
- `shared/ts/calendar` (TypeScript) and `core/calendar` (Python) both implement EC ↔ GC conversion (13 months: 12 of 30 days, plus Pagume with 5 or 6 days) and formatting in Amharic and English month names. Implement the algorithm directly with unit tests rather than trusting a random dependency. **Verify the test vectors against two independent authoritative sources** (including the new-year dates around leap years).
- A school setting chooses `ethiopian`, `gregorian` or `both` for display. A shared date-picker component supports both. Documents and reports can print either or both.
- Academic years, terms and deadlines are stored in GC and displayed in the chosen calendar.

### 5.8 Person and name model

Ethiopian naming: **given name, father's name, grandfather's name.** There is no "last name" field anywhere.

`persons` is the shared base for students, staff and guardians:

| Field group | Fields |
|---|---|
| Name (Latin) | `given_name_en, father_name_en, grandfather_name_en` |
| Name (Ge'ez) | `given_name_am, father_name_am, grandfather_name_am` |
| Optional | `mother_name_en/am, baptismal_name, nickname` |
| Other | `sex, date_of_birth, place_of_birth, nationality, phone, email, address, photo_file_id, custom JSONB` |

- At least one script is required. The UI nudges the user to fill both because certificates usually need the Amharic version.
- **Display rules:** `full_name(person, locale)` returns the three parts in the active locale's script, falling back to the other script. `short_name` is given + father's name. Lists use the short form, official documents use the full form.
- **Search:** one normalized search column covering all name fields in both scripts (with Ge'ez normalization, such as treating common variant characters consistently, and Latin lowercase/transliteration variants). Fuzzy matching through `pg_trgm`.
- **Duplicate detection** at registration: same three names plus date of birth, or phonetically similar plus same DOB, raises a warning.
- **AI transliteration suggestion** is optional, requires human confirmation, and is flagged `needs_review`.

### 5.9 Money

- Currency is **ETB only**. Amounts are `BIGINT` santim. Library `shared/ts/money` and `shared/py/money.py` provide parse, format (e.g. `ETB 1,250.00` or Amharic label `ብር`), add, and allocate (rounding-safe splitting).
- Tax settings (VAT, withholding) are **configuration**, never constants. Nothing about Ethiopian tax or pension rates is hard-coded. They must be validated by the school's accountant.

### 5.10 Configuration system

Layered key-value settings with a typed schema per module: `default (code) < central (CP) < instance (school)`. The settings UI is generated from each module's `settings_schema`. Every change is audited. Key setting groups:

- `school_profile`: name, logos, address, contact, timezone, default language, enabled languages, calendar display.
- `academic_scope`: `first_level`, `last_level` (see 9.1), term system (`semester` or `quarter`), attendance mode.
- `curriculum_profile`: chosen template and its overrides.
- `branding`: theme choice and brand colors.
- `ai`: provider, model, encrypted key, limits.
- `modules`: enabled flags.

### 5.11 Design tokens and themes

- A **theme** is a JSON set of design tokens (colors in OKLCH or hex, radius, fonts, spacing, chart colors, sidebar colors) with a `light` and a `dark` variant. Tokens follow shadcn/ui and Tailwind v4 CSS-variable conventions, so community themes (tweakcn and similar editors and registries) can be imported.
- Defaults shipped: **Light** and **Dark**.
- **Theme Manager:** import by pasting CSS variables, uploading JSON, or pasting a shadcn registry URL. Validation on import: both modes present, required tokens present (including chart and sidebar tokens), and an automatic **WCAG contrast check** on key pairs. A failing theme is rejected or warned, and a broken theme always falls back to the default.
- Scope: the CP can set a school's default theme and brand. School admins choose which themes are available. Each user chooses theme and light/dark mode.
- **Canonical form is JSON in `shared/ts/tokens`.** The build generates CSS variables for web and a typed theme object for React Native from the same source.

### 5.12 Files

S3-compatible storage with signed URLs. A `files` table stores metadata (owner entity, mime, size, checksum, uploader). Validate type and size on upload. Student documents and photos are private by default. Image thumbnails are generated by a background job.

---

## 6. Action registry (the foundation of the AI layer)

Every operation worth exposing is a registered **Action**:

```python
@action(
    key="students.register",
    module="students",
    permission="students.record.create",
    risk="write",  # read | write | bulk | destructive
    input=RegisterStudent,
    output=StudentOut,
    describe="Register a new student",
    preview=preview_register_student,
)
async def register_student(ctx: ActionContext, data: RegisterStudent) -> StudentOut: ...
```

- REST handlers, the AI assistant and automation rules **all call the same action functions**. There is no separate AI-only logic.
- The AI tool list is generated from the registry, filtered by (module enabled ∩ user's permissions ∩ risk policy).
- `risk != read` actions provide a `preview()` that returns a human-readable diff or a dry-run count.
- `ActionContext` carries the acting user, `via`, session and request id, so audit entries are accurate.

---

## 7. AI layer

**Provider-agnostic.** An `LLMProvider` interface (`chat`, tool calling, streaming) with adapters for Anthropic, OpenAI and Google. The school enters its provider, model name (configurable, not hard-coded) and API key.

- **Key storage:** AES-GCM encryption with a per-instance master key from the environment. The key is never returned to any client (masked display only). The CP can disable AI per school (kill switch).
- **Conversation flow:** user message → orchestrator builds the tool list from the registry → model returns tool calls → `read` actions run immediately → anything else becomes an **`ai_proposal`** with a preview → the user confirms in the UI → the action executes **as that user** with `via=ai` and `ai_session_id`.
- **Bulk threshold:** actions affecting more than N records (configurable) always require explicit confirmation showing the count.
- **Prompt-injection defense:** file contents, student notes, messages and tool outputs are passed to the model as clearly delimited *untrusted data*. The model cannot call tools outside the filtered list, cannot alter permissions, roles, AI keys, audit settings or module toggles (those actions are marked `ai_forbidden`), and has a step limit per turn.
- **No free-form SQL.** Natural-language reports run through parameterized **report actions** (e.g. `reports.attendance_below(threshold, period, scope)`), never raw queries.
- **Limits and cost:** per-user rate limits and per-school token counters shown in settings.
- **Voice:** speech-to-text by the device/browser by default (free), with an optional provider-based option. Amharic recognition quality varies by platform, so typed input is always available and transcripts are shown for correction before running. Optional text-to-speech.
- **AI features by phase:** assistant with actions; content translation (section 5.6); name transliteration suggestions; report-card comment drafts; at-risk student alerts; natural-language reports; later: document data extraction at admission, template-from-image, handwritten mark-sheet reading.

---

## 8. Control Plane and the instance link

### 8.1 What the Control Plane does
School registry and provisioning, the **school directory** for the mobile app, the **push relay**, plans and licensing, module toggles per school, version rollout, monitoring, audit vault and oversight, support sessions, backups visibility, and **the owner's own revenue in ETB** (subscriptions, invoices to schools, payments, MRR/ARR).

### 8.2 Enrollment
The CP creates an instance record and a one-time **enrollment token**. On first start the instance generates its own Ed25519 keypair and calls `POST /enroll` with the token and its public key. The CP stores the public key. The instance stores the CP's public key.

### 8.3 License
The CP issues a **signed license** (EdDSA JWT): `{instance_id, plan, modules[], limits{students, staff, storage_gb}, status(active|grace|suspended), valid_until, issued_at}`. The instance verifies it **offline** against the embedded CP public key and refreshes it through heartbeats. If the CP is unreachable, the last valid license continues to work until `valid_until + grace`. `suspended` blocks logins except Super Admin read-only export, per policy.

### 8.4 Heartbeat
Every few minutes: version, uptime, error counts, queue depth, DB size, storage used, student and staff counts, last backup status, audit chain head. The CP responds with config, license refresh and pending commands (such as "upgrade available").

### 8.5 Audit shipping
`audit_outbox` → batches of `(seq range, entries, chain head)` → `POST /audit/ingest` (signed, idempotent). The CP verifies chain continuity and stores entries in the vault. Gaps and hash mismatches raise alerts.

### 8.6 Controller session (acting as a school admin)
The owner opens a school from the CP, supplies a **reason**, and the CP issues a **short-lived signed support token** (minutes, single instance, optional read-only mode). The instance verifies the signature and creates a session with `actor_type=controller`, mapped to the Super Admin permission set. No school password is ever shared. Everything done is audited with `via=controller` and the CP user id. The school may be notified according to policy.

### 8.7 Deployment and upgrades
Phase one: scripted provisioning (`deploy/provisioning`): create the compose project, env file, DB, storage bucket, domain, then enroll. Upgrades: backup → pull images → `alembic upgrade heads` → health check → rollback by restore if needed. Later (optional): an instance agent that executes signed upgrade commands from the CP.

### 8.8 Instance size profiles
`small`, `standard`, `large` presets set worker concurrency, DB resources and cache sizes. A 300-student school and a 3,000-student school differ only by profile. Heavy jobs (term-end report cards) always run in the background queue.

### 8.9 School directory and the single mobile app

One mobile app (iOS and Android, built from `owner/mobile`) serves **every** school. Web users simply open their school's URL.

- **Choosing a school:** the user enters a **school code** or scans a **QR code** (`erpapp://school/<code>`). Searching by school name is optional, **off by default** (it would expose your customer list) and can be enabled per school.
- **Resolve:** the app calls the controller `GET /directory/resolve?code=...`. The controller returns a **signed record**: `{instance_id, name, api_base_url, logo_url, status, min_app_version, kid, signature}`. The signing key is identified by `kid`, so keys can be rotated and the app can hold a set of trusted keys.
- **Trust:** the app embeds the controller's public key set and **verifies the signature**. It only ever connects to servers that came from a verified record. HTTPS is required (local-network addresses are allowed only in development builds). Unknown or revoked codes return a generic error, and resolving is rate-limited to prevent enumeration.
- **Then the app talks directly to the school's server.** The controller only does the lookup. It never sees passwords, school data, or user activity beyond "this code was resolved."
- **Branding:** after resolving, the app fetches the theme from the school's own `GET /themes/active` and applies the school's logo and theme tokens.
- **Several schools on one phone** (a parent with children at two schools, a teacher at two): each school has its own account. Tokens, cached data and the offline outbox are **namespaced per school**. Removing a school wipes its local data. Optional biometric/app lock.
- **Directory outage:** existing users keep working from their stored, previously verified school profile.
- **White-label (later, not built):** a build-time `APP_VARIANT` hook (name, icon, fixed school code) is kept possible so a large school could someday get its own branded app.

### 8.10 Version compatibility

Schools upgrade at different times, so one app will meet servers on different versions.

- **Policy:** within `/api/v1`, changes are **additive only**. Breaking changes require `/api/v2`, served alongside the old version for a defined period. Deprecations stay for at least two releases.
- **Handshake:** `GET /api/v1/system/info` (public) returns `api_version`, `app_version` and `min_client_version`. After login, `GET /api/v1/system/capabilities` lists the features this server supports. The app hides what the server lacks and shows a gentle "school is on an older version" state.
- **Forced update:** if the app is older than `min_client_version` (set globally or per school in the CP), it shows an update screen.
- **CI guard:** an OpenAPI schema snapshot per release with an automatic breaking-change check.

### 8.11 Push notifications through the controller

- The mobile app registers its device token with the controller for a (school, user pseudonym) pair. School instances send push requests to the controller (`POST /push/send`, signed), and the controller delivers through the push provider (Expo push or FCM/APNs). **Push credentials live only in the controller**, so schools hold none.
- **Payloads are minimal** (for example "New message", "Results published") with a deep link. No marks, names or amounts travel through push. Delivery is best-effort with retry, and the in-app notification center remains the source of truth.
- A school can only push to devices registered under that school. Invalid tokens are cleaned up automatically. Every push is logged in the CP.

---
## 9. Domain modules

### 9.1 Academics: structure, curriculum and scope (`academics`)

- **Grade levels:** an ordered catalog (`KG1, KG2, KG3, Grade 1 … Grade 12` by default, editable). Each school sets `first_level` and `last_level`, so the system can run KG only, Grade 1–5, KG–12, or anything else. Everything else (sections, fees, timetable, mark structure, documents, promotion) only offers levels inside the school's scope.
- **Stages:** configurable groupings of levels (default: KG, Primary 1–4, Primary 5–8, Secondary 9–10, Preparatory 11–12). Used for reporting and to attach rules to a stage rather than to each level. Defaults are editable and must be marked "verify against the school's actual structure."
- **Academic years** and **terms.** The school chooses `semester` or `quarter`. Terms have start and end dates (displayed in EC or GC), and open/closed states.
- **Sections** (class groups) per level per year, with homeroom teacher and capacity. **Subjects** with per-level assignment and optional credit/weight. Subject groups (e.g. electives).
- **Curriculum profile:** a bundle chosen by the school at setup: subjects per level, term system, mark-structure template, grade scale, promotion rules, and default document templates. Shipped templates: *Ethiopian National*, *Private: Custom*, *International: Generic*. The shipped contents are **starter data only**, flagged for verification by the school or an official source, and fully editable. A school can duplicate and modify a profile.
- Changing the profile after data exists warns about impact and applies only from a chosen academic year forward.

### 9.2 Students and admissions (`students`, `admissions`)

- **Student record** = `person` + `student_profile` (student number, status) + `enrollments` (per academic year: level, section, status, roll number) + guardians (many-to-many with relationship, primary contact, can-pickup) + medical + documents + custom fields.
- **Statuses:** applicant, active, promoted, repeating, transferred out, withdrawn, graduated, alumni.
- **Student ID:** configurable format (e.g. `{SCHOOL}-{YYYY}-{SEQ:5}`), generated atomically.
- **Admissions workflow:** configurable application form (custom fields), document upload, optional entrance test with score, decision steps (applied → reviewed → test → offered → accepted → enrolled), auto-assignment to level and section by rule, guardian account creation, welcome notification, first invoice (through automation).
- **Promotion and transfer:** bulk promotion at year end by rule (using the promotion rules from 9.5), manual exceptions, transfer-out certificate generation, alumni conversion.
- **Duplicate detection** per section 5.8.

### 9.3 Staff and HR (`staff`)

- Staff profile on `person`: positions, departments, employment contract (type, dates, salary info), qualifications, documents.
- **Teaching assignments:** teacher ↔ subject ↔ section ↔ academic year. These drive scopes such as `assigned_subjects` and `own_class`.
- Leave types, balances, requests and approvals. Staff attendance.
- Optional **payroll sub-module**: salary components, payslips in ETB. Income tax and pension calculations are fully configurable rules with no hard-coded rates.
- Roles are assigned here or in Settings. Users link to staff profiles.

### 9.4 Attendance (`attendance`)

- Mode per school: **daily** or **per period** (the latter needs the timetable module).
- Statuses: present, absent, late, excused (with reason). Fast entry by section on web and mobile (default everyone present, mark exceptions only). Works offline on mobile.
- Events: `attendance.absent_marked` triggers automation (parent notification). Reports: by student, section, period, threshold alerts.

### 9.5 Assessment: marks, grading and results (`assessment`)

This module has five parts. **Marks are numeric inputs by teachers, converted by structure rules set by the school's leaders.**

#### 9.5.1 Mark structure (set by authorized higher-ups)

- `assessment_structures` define, per school or per level/stage or per subject, **for an academic year**:
  - `term_system` (semester/quarter) inherited from academics.
  - **Components**, each with `key`, label (translatable), `max_points` and `aggregation`. Example: Participation 10, Quizzes 10, Assignments 10, Mid-exam 20, Final exam 50 (total 100). Schools set their own totals, such as 60 or 40.
  - **Aggregation modes** for several assessments inside one component: `average`, `weighted_average`, `best_n`, `sum_capped`, `latest`.
  - **Year result rule:** how terms combine (average, sum, weighted).
  - **Rounding and precision** (decimal places, rounding mode, half-up default).
- Changing a structure for a year that already has marks shows an impact preview and triggers a background **recalculation job** (raw data is never modified).
- **Descriptive mode** for KG and lower grades: ratings (e.g. Developing / Achieved) instead of numbers, driven by a rating scale.

#### 9.5.2 Teacher entry and conversion

Teachers create an **assessment** (`title, component, subject, section, date, out_of, weight?`) and enter each student's **raw score**.

For each score the system stores: `raw_score`, `out_of` (copied from the assessment), `status` (`present | absent | excused | exempt | not_taken`), and `converted` (recomputed, never user-typed).

```
percent_i      = raw_i / out_of_i                       (only for status = present)
component_val  = aggregate(percent_1..n) × component.max_points
term_total     = Σ component_val
```

Absent, excused, exempt and not-taken are not zeros. Whether `absent` counts as 0 or is excluded is a school setting (default: configurable per component). Validation rejects `raw > out_of` unless bonus marks are enabled for that assessment. All calculations are pure functions in `assessment/engine.py` using `Decimal`, with heavy unit tests (see section 14).

#### 9.5.3 Grade rules (the grading rule engine)

A school can define **any number of grade scales** and attach them by context.

- `grade_scales(id, name, type[numeric_bands|descriptive], is_default, effective_from, effective_to, rounding)`.
- `grade_scale_bands(scale_id, min_value, label, remark, gpa_points, is_pass, color, sort_order)`.
  - Bands are stored as half-open ranges `[min, next_min)`, with the top band closed. The editor shows "from X to Y", auto-adjusts neighbors, and **validates full coverage of the scale range with no gaps and no overlaps**.
  - Example: 90+ → A+, 85–<90 → A, 75–<85 → C+ (the school can split or merge as it likes).
- **Scale assignment order (most specific wins):** assessment context (e.g. a special official/national test) > subject > level > stage > school default.
- A **test tool** in the editor: type a value and see the resulting label.
- Changing a scale never alters raw or converted marks. It changes labels. Published results store the **scale version used**, so history stays reproducible. Re-publishing is an explicit, audited action.
- **Result rules:** pass/fail rules (minimum total, minimum per subject, maximum failed subjects), rank calculation (ties handled by a school setting), and **promotion rules** (e.g. promote if average ≥ X and failed subjects ≤ Y), reused by 9.2.

#### 9.5.4 Workflow and control

States: `draft → submitted → approved → published → locked`.

- **Marking windows:** leaders open and close entry per term and level with deadlines. Automatic reminders to late teachers.
- Teachers submit. A department head or academic head reviews and approves, then the results are **published** to parents and students. Schools can shorten the chain.
- **After lock**, edits require a **correction request** (reason, old → new value) that an approver accepts or rejects. Everything is audited.
- **Progress dashboard** for managers: per section and teacher, entry completion, overdue, and flagged anomalies (identical marks for a whole class, average far from the norm). Anomalies are warnings, not blocks.

#### 9.5.5 Entry UX (see section 11.3)

Spreadsheet-style grid on web, one-hand fast entry on mobile, Excel paste and upload, offline mobile entry, live converted preview and class statistics. AI voice and photo shortcuts come later through the action registry.

### 9.6 Timetable (`timetable`)

- Entities: rooms (capacity, type), period definitions (days, slots, breaks), teacher availability, subject periods per week per section, constraints.
- **Hard constraints:** no teacher/room/section double-booking, availability, room capacity and type, per-subject weekly load. **Soft constraints (weighted):** spread subjects across days, avoid last-period for heavy subjects, minimize teacher gaps, double periods where required.
- **Solver:** OR-Tools CP-SAT in a background job with a time limit, progress and explainable failure ("could not place Math for 7B: teacher X unavailable").
- Manual drag-and-drop editing with live conflict checking, locking of chosen slots before regeneration, **versions** (draft/published), and substitute-teacher handling for absences.
- Outputs: per teacher, section, room, in the web app, the mobile app and printable PDFs.

### 9.7 Fees and payments (`fees`)

- **Fee structures** per level and year: items (tuition, registration, transport, activities…), schedule (monthly, term, yearly, custom installments), due dates, late-fee rules.
- **Discounts and scholarships** (sibling, staff child, merit, custom), approval for discounts.
- **Invoices**, **payments**, **allocations** (a payment can cover several invoices), **credits**, **receipts** (numbered, PDF through Document Studio), refunds, arrears and automated reminders, accountant reports (collections, outstanding, by level, by method) all in ETB.
- **Payment adapter interface** (`shared/py/payments.py`): `create_checkout(invoice) → redirect/instructions`, `verify(reference) → status`, `handle_webhook(request) → event`, optional `refund`. Providers implemented behind it:
  - **`manual_bank`** (parent submits bank reference and optional slip image, accountant verifies and reconciles) and **`cash`** first.
  - **Gateway adapters**, activated only when credentials are supplied (until then they are disabled stubs with sandbox-ready code): **Chapa, ArifPay, SantimPay**, direct **telebirr** and **CBE Birr** where merchant APIs are available, and EthSwitch's national gateway later.
  - Rules for every adapter: signed-webhook verification, idempotent processing, amount and currency re-verification with the provider, status polling fallback, raw payload logging (encrypted credentials), and the ability to run more than one provider at once.
  - The Ethiopian gateway sector has seen regulatory disruption (bank account freezes and tax enforcement disputes were reported in late 2025 and 2026). **Never depend on one provider.** Re-check each provider's current API docs, licensing and status before integrating.
- Fees data feeds the school's dashboards. The same adapter library is used by the CP for subscription billing.

### 9.8 Document Studio (`documents`)

Design printable documents on a canvas and generate PDFs filled from system data.

- **Document types:** report card, transcript, certificates (completion, merit, appreciation, for students and staff), ID card, admission letter, receipt, invoice, experience letter, custom.
- **Canvas editor (web, desktop):** text, images, shapes, lines, tables, logo, backgrounds, QR code, barcode, signature/stamp/photo placeholders. Page presets (A4, A5, Letter, portrait/landscape, custom size such as ID cards), margins, bleed. Fonts: bundled Ethiopic fonts plus uploaded fonts. Snap, align, layers, undo/redo.
- **Fields:** `{{student.full_name}}`, `{{student.grade}}`, `{{date.issued|ec}}`, `{{fees.amount|etb}}`, etc. **Each module registers the fields it offers**, so a field appears only if its module is on. Fields support formatting options (calendar, script, locale).
- **Repeating tables** (e.g. subjects × components/terms) with totals, average, rank, attendance and remarks. **Conditions** (show "Promoted" or "Repeat" blocks, hide empty sections).
- **Layout format:** our own JSON schema (elements with positions in millimetres, styles, bindings). A server-side renderer converts it to HTML/CSS and then PDF, so **the canvas preview and the printed result match**.
- **Generation:** single or bulk (a whole section/grade) as separate files or one combined PDF, through background jobs. Each issued document records `template_id`, `template_version`, a **data snapshot**, number, issuer and date, so reprints are identical years later. QR codes link to a public verification page (`/verify/{code}`) showing only minimal data.
- **Workflow:** draft/publish templates. Optional approval before issuing certificates. Separate permissions for **design**, **generate** and **approve**.
- **Starter library** of templates, import/export of templates as files, and templates pushed from the CP to all schools, which each school can duplicate and customize.
- **AI (later):** describe a certificate in words for a draft layout; upload a photo of an existing paper report card to get a starting template.

### 9.9 Communication and portals (`communication`, `portals`)

- Announcements with audience targeting (school, level, section, role), scheduling and attachments. Parent–teacher messaging with school-configurable moderation.
- Notification templates (translatable) and a delivery log across channels (section 5.5).
- **Parent portal** (multi-child) and **student portal**: published marks and report cards, attendance, timetable, fees with online payment, announcements, issued documents. Available on web and mobile, and visible only if the module is enabled and the user's role permits.

### 9.10 Automation (`automation`)

- Rules: `trigger (domain event) + conditions (JSON-logic) + actions (registered actions or notifications)`, with optional delay and schedule triggers (cron-like).
- Rules run as an `automation` actor limited to a chosen permission set (`run_as`). **Dry-run mode**, run history with outcomes, loop and recursion guards, per-rule enable switch.
- Starter rules: student admitted → account, class, welcome message, invoice; absence → notify guardian; marking deadline approaching → remind teacher; term closed → compile report cards and notify parents; invoice overdue → reminder.

### 9.11 AI assistant module (`ai`)

The chat panel (web and mobile), voice input, proposals/confirmations, settings (provider, key, limits), usage view. Behavior as in section 7.

### 9.12 Add-on modules (later)

Library, transport, inventory, hostel, health clinic, events. Each follows the module system and ships only after the core is complete.

---

## 10. Data model overview (core entities)

Naming: plural snake_case tables. All business tables include `id, created_at, updated_at, created_by, updated_by, deleted_at, deleted_by, row_version`.

| Area | Tables |
|---|---|
| Core | `users, sessions, roles, role_permissions, user_roles, user_permission_overrides, delegations, settings, instance_modules, license_state, locales, translation_entries, content_translations, themes, files, notifications, notification_templates, delivery_logs, jobs, domain_events_outbox, idempotency_keys, custom_field_defs` |
| Audit | `audit_log` (append-only, hash chain), `audit_outbox`, `ai_sessions, ai_proposals` |
| People | `persons, student_profiles, staff_profiles, guardians, student_guardians, medical_records, person_documents` |
| Academics | `grade_levels, stages, academic_years, terms, sections, subjects, level_subjects, curriculum_profiles, enrollments` |
| Staff | `departments, positions, contracts, teaching_assignments, leave_types, leave_balances, leave_requests, staff_attendance` |
| Attendance | `attendance_sessions, attendance_records` |
| Assessment | `assessment_structures, structure_components, assessments, scores, score_revisions, term_results, result_snapshots, grade_scales, grade_scale_bands, grade_scale_assignments, result_rules, promotion_rules, marking_windows, mark_submissions, correction_requests` |
| Timetable | `rooms, period_defs, availability, subject_loads, tt_constraints, tt_versions, tt_slots, substitutions` |
| Fees | `fee_items, fee_structures, fee_schedules, discounts, invoices, invoice_lines, payments, payment_allocations, credits, refunds, payment_provider_configs, payment_events` |
| Documents | `doc_templates, doc_template_versions, issued_documents, doc_fields_registry` |
| Communication | `announcements, message_threads, messages` |
| Automation | `automation_rules, automation_runs` |

**Controller DB:** `cp_users, cp_roles, schools (instances), plans, plan_modules, licenses, enrollments, heartbeats, vault_audit_entries, vault_chain_heads, alerts, support_sessions, school_codes, directory_keys, push_devices, push_log, subscriptions, school_invoices, school_payments, versions, rollouts`.

**Database safeguards:** foreign keys everywhere, check constraints for money ≥ 0 and score ranges, partial indexes excluding soft-deleted rows, `pg_trgm` indexes for name search, unique business keys (student number, invoice number, document number) scoped appropriately, and a DB role for the app without UPDATE/DELETE on `audit_log`.

---
## 11. Frontend architecture

### 11.1 Shared principles
- **Shell:** sidebar/tab navigation generated from `GET /me/navigation` (module registry ∩ enabled ∩ permitted). Nothing is hard-coded in menus.
- **Command palette** and the **AI assistant panel** are available everywhere (if the AI module is on and permitted).
- Server state in TanStack Query. Forms in React Hook Form + Zod, with server validation errors mapped to fields.
- Every string through i18n. Every color and radius through tokens. Every date through the calendar layer. Every amount through the money layer.
- Responsive and accessible (keyboard navigation, focus states, ARIA, contrast). Ethiopic text tested in every key screen.
- Tables: server-side pagination, sorting, filtering and saved views. Virtualization for long lists.

### 11.2 Apps
- **`school-erp/web`:** the school app (staff, teachers, parents, students) and the desktop experience. Responsive, PWA behavior. Each school's web address is its own instance.
- **`owner/controller-web`:** the CP UI (separate app, separate deployment).
- **`owner/mobile`:** **one Expo app for all schools** (see §8.9) for teachers, staff, parents and students. It has a school picker, an account switcher and the module screens, and uses the same generated API client, tokens and i18n runtime loader as the web app.

### 11.3 Mark-entry experience (critical UX)

**Web grid**
- Rows = students (photo, short name), columns = assessments of the chosen component/subject/section. Cell editing with keyboard: type, Enter (down), Tab (right), arrows to move, Esc to revert, `A` for absent, `E` for excused, `-` for not taken.
- Live converted value next to each raw score. Footer shows class average, highest, lowest, entered/total, and flagged cells (over max, missing).
- **Autosave** per cell with a visible saved/pending/failed indicator and conflict handling through `row_version`.
- Paste a column or block from Excel (TSV). Download a prepared sheet and upload it back with a validation step before commit.
- Teachers see only their assigned sections and subjects. Locked or closed windows are clearly shown as read-only with the reason and a "request correction" action.

**Mobile**
- Two modes: **card mode** (one student at a time, photo and name large, numeric keypad, auto-advance) and **list mode** (compact rows). A persistent running count and a submit button.
- **Offline-first:** entries go to the local outbox immediately, sync in the background, and show per-row sync status. Conflicts return a clear "changed by someone else" resolution step.

### 11.4 Mobile offline strategy
- Persisted query cache for read data. A **mutation outbox** (SQLite) for offline-capable actions: attendance, mark entry, announcements read, simple messages. Each queued mutation has an idempotency key and a base `row_version`.
- Sync worker with retry and backoff, visible sync status, conflict UI. Anything not safe to queue offline (payments, role changes, deletions) is online-only.
- The cache and outbox are **namespaced per school** (§8.9), so queued actions can never be sent to the wrong school's server.

---

## 12. Security and privacy

- **Targets:** OWASP ASVS level 2 for the web/API. Security headers, strict CORS, CSRF protection for cookie auth, rate limiting, input validation everywhere (Pydantic), output encoding, file upload validation, SSRF-safe outbound calls.
- **Secrets:** never in git. `.env.example` only. Production secrets via the host's secret mechanism. AI keys and payment credentials are encrypted at rest with the instance master key. Key rotation procedure documented.
- **Data about minors is sensitive:** least-privilege scopes by default, read-audit of sensitive records, signed short-lived file URLs, encrypted backups, configurable retention. **Have a local lawyer review compliance with Ethiopian personal-data-protection requirements** before launch.
- **Isolation:** one database and one set of secrets per school. A compromised instance cannot reach another school's data. Instances only talk to the CP, and the CP never stores school business data beyond audit entries and metrics.
- **Controller sessions:** short-lived, reasoned, scoped, fully audited. CP accounts require 2FA.
- **Backups:** nightly encrypted dumps plus object storage sync, retention policy, and **tested restores** (a restore drill is part of the production checklist).
- **Dependency hygiene:** lockfiles, automated vulnerability scanning in CI, and a policy to avoid very recently published package versions.

---

## 13. Deployment and operations

- **Per-instance compose project** (`api`, `worker`, `beat`, `postgres`, `redis`, `minio` or external S3, `web` static, `caddy`). Project name = instance slug. Separate env file and volumes. Multiple instances may share a host with distinct domains and internal networks. Resource limits by size profile.
- **Environments:** `dev` (local, seeded demo data), `staging` (optional), `production`.
- **Health:** `/health` (liveness) and `/ready` (DB, Redis, storage, migrations at head). Structured JSON logs with request ids. Optional Sentry-compatible error reporting. Metrics endpoint for heartbeats.
- **Release process:** CI builds versioned images and mobile builds (EAS). Staged rollout from the CP: one pilot school first, then the rest. Migrations are backward-compatible for one version where possible.
- **Runbooks** in `docs/runbooks`: provisioning a school, upgrading, restoring from backup, rotating keys, suspending a school, investigating audit-chain alerts.
- **Capacity notes:** expected year-one scale is 1–5 schools of mixed size (hundreds to several thousand students). A single modest server per instance (or a few instances per larger server) is sufficient. The design must not block later growth, but do not build Kubernetes-style orchestration now.

---

## 14. Testing and quality strategy

| Layer | Tooling | What it must cover |
|---|---|---|
| Pure logic | pytest | Mark conversion, aggregation modes, rounding, grade-band resolution and validation, rank/ties, promotion rules, Ethiopian calendar conversion, money allocation, license verification, hash chain |
| API integration | pytest + httpx + real Postgres | Every endpoint: success, validation error, permission denied, module disabled, soft delete, audit entry written |
| Permission matrix | Generated tests | Every route × every default role; fails if a route has no declared permission |
| Migrations | pytest | Empty DB → head; previous release → head; downgrade where supported |
| Frontend units | Vitest + Testing Library | Components, hooks, calendar and money packages, grid keyboard behavior |
| i18n | script | No missing `en` keys, report of missing `am` keys, no hard-coded strings (lint rule) |
| E2E web | Playwright | Critical journeys: login, module toggle effect on menu, admission → student, mark entry → publish, certificate generation, fee payment (manual), controller → open school |
| Mobile | Jest + Maestro (optional) | Login, mark entry offline → sync, attendance |
| Performance | k6 or Locust | Mark entry concurrency, bulk PDF for ~3,000 students, student search latency, timetable solve time |
| Security | scanners + manual checklist | Dependency audit, auth tests, IDOR tests on every ID-based endpoint |

**Quality gates (every phase):** lint, type check, unit and integration tests, build of all apps, i18n check, and the phase's smoke script all pass. Tests are never deleted or weakened to get green.

---

## 15. Delivery roadmap (phase summary)

| Phase | Theme |
|---|---|
| 0 | **Walking skeleton:** every connection proven with thin code |
| 1 | Foundations: full auth/RBAC, audit and history, persons and names, i18n editor, themes, settings, calendar, money, files |
| 2 | Academic structure, curriculum profiles, students and admissions |
| 3 | Staff/HR, teaching assignments, attendance |
| 4 | Assessment: mark structure, conversion, grade rules, entry UX, workflow, results |
| 5 | Document Studio |
| 6 | Timetable |
| 7 | Fees and payments |
| 8 | Communication and portals |
| 9 | AI layer (assistant, providers, voice, translation and AI features) |
| 10 | Automation engine |
| 11 | Control Plane completion (licensing, provisioning, monitoring, audit vault, billing in ETB, school directory, push relay) |
| 12 | The single multi-school mobile app: completion, offline hardening, version handshake, store release |
| 13 | Add-on modules (optional) |
| 14 | Hardening and production readiness |
| 15 | Final dev launcher, seed data, documentation, release |

The dev launcher and demo accounts exist from phase 0 and grow each phase, so the owner can test everything built so far at every checkpoint.

---

## 16. Decision log and items to verify

**Decided**
1. Modular monolith, one DB per school, Docker Compose per instance.
2. All migrations always applied. Modules gated at runtime, never by schema.
3. Dates stored in Gregorian. Ethiopian calendar is a display/input layer.
4. Money as integer santim, ETB only.
5. Marks: raw score and "out of" always stored. Converted values are derived and recomputable.
6. School-visible audit = Tier A (business activity). Technical logs and the immutable vault are controller-only.
7. English default, Amharic in phase one. Afan Oromo and Tigrinya added later as translation data.
8. Payments behind an adapter interface. Manual bank and cash first. Gateways enabled once credentials exist.
9. **One repo, three zones** (`school-erp/`, `owner/`, `shared/`) with enforced boundaries. Splitting later is a documented, mechanical step.
10. **One mobile app for all schools**, using a signed school directory hosted by the controller, with per-school isolated storage.
11. API stays backward compatible within `/api/v1` (additive only), because schools run different versions.
12. Push notifications go through the controller with minimal payloads.

**To verify during the build (do not assume)**
- Ethiopian calendar conversion test vectors (two independent sources).
- Which PDF renderer correctly shapes and embeds Ge'ez text (spike P0-23).
- Starter data for the "Ethiopian National" curriculum profile and stage groupings (mark as unverified, school edits).
- Current API documentation and sandbox availability of each payment provider, and their regulatory status.
- SMS provider options for Ethiopia (adapter first, provider later).
- Amharic speech-recognition support on browsers and mobile platforms.
- Ethiopian personal-data, tax and pension requirements, reviewed by qualified local professionals.

**Open owner decisions (can be answered later; defaults apply meanwhile)**
- Whether school Super Admin actions appear in the school's activity history (default: no).
- Whether schools are notified when a controller support session happens (default: yes, configurable per school).
- Whether Afan Oromo and Tigrinya are priority after launch.
- Whether a large school may later get its own branded app (the build keeps a variant hook, but the feature is not built).
