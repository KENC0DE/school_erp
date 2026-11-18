# Reconciliation report: v1 documents → v2 documents

Date: 2026-11-18
Branch: `reconcile-v2`
Baseline commit: `66c013c` (WIP snapshot) on top of `aba0912`.

This file records the Stage A baseline, the exact difference between the archived
v1 specifications and the new documents, the mapping from the old layout to the
new one, and what was re-verified or is still open.

## Baseline (before any reconciliation change)

The working tree was dirty when this session started (the students numbering work
from P2-07, the updated documents and a new `docs/archive/v1/`). It was committed
as `WIP snapshot before reconciliation` so every later step can be undone.

The repository was **already laid out as `school-erp/` + `owner/` + `shared/`**;
the v1 guide that the previous sessions built from already contained the
three-zone design, the signed directory and the single mobile app. No directory
had to be moved. `docs/archive/v1/` holds the true v1 documents.

| Check | Result at baseline |
| --- | --- |
| `./scripts/dev.sh test` | all 8 steps pass |
| school backend `pytest` | 252 passed |
| controller `pytest` | 10 passed |
| shared Python + zone-boundary `pytest` | 45 passed |
| `ruff check` / `ruff format --check` | clean |
| `import-linter` | 4/4 contracts kept |
| `pnpm -r test` | school web 61, controller web 13, mobile 27, shared TS suites pass |
| `pnpm -r typecheck` | clean |
| `pnpm -r lint` | clean |
| `pnpm -r build` | school web and controller web build |
| `python3 scripts/check-i18n.py` | 1073 keys, 525 referenced, 0 missing |
| `python3 scripts/check-api-compat.py` | 95 released paths compatible |
| `bash scripts/gen-api.sh` + diff | committed client already current |
| `./scripts/dev.sh reset` + `seed` | 11 school accounts, 2 controller accounts, school code `DEMO` |
| `./e2e/run.sh` | **2 of 3 failed at first** (see below); fixed, then 3/3 pass |

Host limitations (unchanged): no Docker daemon, so the SQLite fallback is used;
no PostgreSQL binary; no Expo Go device; no `pwsh`.

### Baseline failures and their resolution

1. **Smoke e2e: ambiguous heading matcher.** After a page reload the school web
   briefly renders raw i18n keys while the bundle loads. `getByRole("heading",
   { name: "Dashboard" })` then matched three headings (`Dashboard`,
   `dashboard.modules`, `dashboard.language_hint`) and Playwright raised a strict
   mode violation. The assertion now uses `exact: true`, which waits for the
   translated heading. This is a more precise assertion, not a weaker one.
2. **Cascading module test.** Because test 1 failed after disabling `sample`, it
   never re-enabled it, so the later settings test saw `licensed = No`. Fixing
   test 1 restored test 3. No product change was needed.

## What changed between v1 and v2

Diffed `docs/archive/v1/*` against `docs/01_PROJECT_ARCHITECTURE.md` and
`docs/02_BUILD_GUIDE.md`.

### New tasks (3)

| Task | Summary |
| --- | --- |
| P0-19b | Web design foundation in `shared/ts/ui-web`: spacing/type/radius/shadow tokens, bundled Latin + Ethiopic fonts with tabular numerals, the full shared kit (buttons, inputs, select, EC/GC date picker, dialog, side sheet, toast, badge, tabs, skeleton, empty/error state, page header, data table, form layout, shell, controller-session banner), three reference screens, `docs/UI_CHECKLIST.md`, token lint rules. |
| P0-21b | Mobile design foundation in `owner/mobile/src/ui` from the same tokens: buttons, inputs, list rows, cards, bottom tabs, sheet, toast, skeleton, empty/error states, school-picker styling, safe areas, 44/48 pt targets, dark mode, three reference screens. |
| P1-27 | UI quality gate automation: Playwright screenshots at 1440/768/390 in light/dark and `en`/`am` with a long-Amharic fixture, axe accessibility scan, loading/empty/error state check, theme import layout check. |

### Changed task text (4)

| Task | Change |
| --- | --- |
| P0-26 | The smoke e2e must also assert that the persistent controller-session banner is visible while acting as a school admin. |
| P14-13 | Now a full visual review of every screen against `docs/UI_CHECKLIST.md`, in addition to the accessibility and i18n pass. |
| P15-07 | "Do not split unless instructed" now points at `docs/OWNER_REQUESTS.md`. |
| P13 intro | Add-ons are built only from `docs/OWNER_REQUESTS.md`; an empty or missing file skips the phase. |

### Process and architecture changes (no task ID)

- GUIDE §0.2 gains rules 16 (UI standards + quality gate) and 17 (autonomous
  operation).
- GUIDE §0.3 Definition of Done gains the screens-only UI quality gate.
- GUIDE §0.7 is new: the autonomy loop, owner-review handling, the three-
  approach rule, stub-and-continue, the narrow stop conditions, and memory files.
- GUIDE §0.4 `dev.sh mobile` explicitly points Expo at the computer's LAN
  address; §0.5 ports are unchanged.
- ARCH §11.5 is new: design principles and UI standards (calm, modern, 8-point
  grid, one accent, light/dark first-class, WCAG AA, standard patterns, mobile
  specifics, Amharic expansion, accessibility, design-foundation-first).
- ARCH §4.4 boundary rules and §8.9–8.11 (directory, version handshake, push
  relay) are unchanged from v1; they were re-read and re-verified.
- ARCH §16 decision log gains item 13 (design).
- ARCH §11.1 mentions spacing through tokens.

The brief listed further tasks (P0-01, P0-01b, P0-04b, P0-16b, P0-21, P0-25,
P1-23, P1-26, P8-06, P11-12, P11-13, P11-SEED, P12-07…P12-10) as changed. The
actual v1→v2 diff shows their text is unchanged; they already contained the
three-zone/one-app/compatibility design that the repository was built against.
They were re-verified where their phase is already reached (P0-01, P0-01b,
P0-04b, P0-16b, P0-21, P0-25, P1-23, P1-26) and stay ticked. P8-06, P11-12,
P11-13, P11-SEED and P12-07…P12-10 stay unchecked until their phase.

## Repository mapping (actual, not hypothetical)

The v1 layout was already identical to ARCH §4.4, so every move is a no-op. The
mapping is recorded for the record:

| v1 path | v2 path | State |
| --- | --- | --- |
| `backend/` | `school-erp/backend/` | already there |
| `apps/web` | `school-erp/web/` | already there |
| `apps/mobile` | `owner/mobile/` | already there |
| `controller/api` | `owner/controller-api/` | already there |
| `controller/web` | `owner/controller-web/` | already there |
| `libs/shared_py` | `shared/py/` | already there (package `erp_shared`) |
| `packages/{api-client,tokens,i18n,calendar,money,module-sdk}` | `shared/ts/<same>/` | already there |
| `packages/ui` | `shared/ts/ui-web/` | **created in P0-19b** |
| `packages/ui-native` | `owner/mobile/src/ui/` | already there; completed in P0-21b |
| `shared/openapi` | `shared/openapi/` | already there |

No reference to `apps/`, `libs/`, `packages/` or `controller/` remains in code,
config, scripts, CI, Docker, Alembic, `.env.example` or `AGENTS.md` (checked with
a repository-wide search excluding build caches). `pyproject.toml`, `pnpm-
workspace.yaml`, tsconfig paths, `scripts/gen-api.sh`, `scripts/check-boundaries.sh`
and `scripts/check-api-compat.py` already point at the new paths.

## Re-verification after reconciliation

| Task | Why | Result |
| --- | --- | --- |
| P0-01 / P0-01b | Zones and boundary enforcement named in the brief | `pnpm install`/`uv sync` layout current; import-linter 4/4 and ESLint restricted imports clean |
| P0-04b | Version endpoints named in the brief | `test_health_system.py` passes |
| P0-16b | Signed directory named in the brief | controller signing/verification/rate-limit tests pass |
| P0-21 | Single multi-school app named in the brief | 27 Jest tests pass (tamper rejection, per-school isolation, verified-profile-only) |
| P0-25 | Dev launcher named in the brief | `reset` + `seed` produce all demo accounts |
| P1-23 | Notification service named in the brief | backend notification tests pass |
| P1-26 | Compatibility guard named in the brief | `check-api-compat.py` 95 paths; wired in CI |
| P0-26 | Text changed (banner) | e2e now passes; banner added under P0-19b and asserted |

## Open items

- Design foundation (P0-19b/P0-21b) and UI gate automation (P1-27) are the real
  new work; tracked in `docs/PROGRESS.md`.
- Existing feature screens are migrated onto the shared kit as part of P0-19b.
- No structural rollback was needed, so nothing is recorded in QUESTIONS.md for
  the restructure.
