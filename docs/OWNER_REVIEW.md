# Owner review log

Items the build guide asks the owner to review. They never block the builder:
each entry records what to look at, how to run it, and what "good" looks like.
The owner files any requested change as a new task.

## 2026-11-18 — Reconciliation baseline

- **What:** the project structure already matches ARCH §4.4
  (`school-erp/`, `owner/`, `shared/`); the updated documents add the design
  foundation, the UI quality gate and autonomous-operation rules.
- **How to look:** `docs/RECONCILIATION.md`.
- **Good:** no structural change was needed; tests, lint, boundaries and the
  smoke e2e are green.

## 2026-11-18 — P0-19b web design foundation

- **What:** the shared web UI kit (`shared/ts/ui-web`) on token-driven
  `ui-*` classes, bundled Inter + Noto Sans Ethiopic, the app shell (sidebar,
  top bar, controller-session banner), and three reference screens — list with
  filters, form with sticky save bar, dashboard — at `/design`.
- **Screenshots:** `docs/review/p0/` — `list|form|dashboard|shell` at 1440, 768
  and 390, light and dark, `en` and `am`, plus `nav-390-*` for the phone drawer.
- **How to look:** `./scripts/dev.sh up && ./scripts/dev.sh seed`, sign in as
  `superadmin@demo.school` / `DevPass#2026`, open **Design reference** in the
  navigation, toggle **Light/Dark** and the language selector.
- **Good:** calm hierarchy, one green accent, 8-point spacing, readable Amharic
  beside Latin, tabular numerals in tables and money, tables stack into cards on
  phones, drawer reachable by keyboard, no horizontal page scroll.
- **Checked against:** `docs/UI_CHECKLIST.md` (all applicable boxes). Known
  open points are listed in `docs/QUESTIONS.md`; none block progress.
- **Automation:** screenshots are reproducible with
  `RUN_DESIGN_SCREENSHOTS=1 pnpm --filter @erp/e2e exec playwright test
  tests/design-screenshots.spec.ts` against a running dev stack. The full UI
  gate (axe, states, theme-layout) lands in P1-27.

## 2026-11-18 — P0-21b mobile design foundation

- **What:** the native UI kit in `owner/mobile/src/ui` (buttons, fields, cards,
  list rows, badges, segmented control, bottom tabs, sheet, toast, skeleton,
  empty/error states, sticky save bar) on the shared tokens; the tab shell with
  a “More” sheet for language, theme and sign-out; and three reference screens
  (list, form, dashboard) in the development-only `Design reference` route.
- **Screenshots:** `docs/review/p0/mobile-*` — list, form and dashboard at
  390×844 and 430×932, light and dark, `en` and `am`, plus the school picker.
- **How to look:** `pnpm --filter @erp/mobile web` (or `./scripts/dev.sh mobile`
  on a device), open the app, then **More → Design reference** in a development
  build. The picker screenshots come from the first screen of the app.
- **Good:** calm native layout, one green accent, 16 px page padding, 48 dp
  touch targets, Amharic and Latin together, filled status badges that meet AA,
  the primary action pinned above the safe area on forms, both languages and
  both colour modes checked on a small and a large phone.
- **Checked against:** `docs/UI_CHECKLIST.md` (all applicable boxes). Known
  open points are listed in `docs/QUESTIONS.md`; none block progress.
- **Automation:** reproducible with `RUN_MOBILE_SCREENSHOTS=1 pnpm --filter
  @erp/e2e exec playwright test tests/design-mobile-screenshots.spec.ts` while
  Expo web runs on port 8081. No device was available, so this is Expo web at
  phone viewports (see `docs/DECISIONS.md`).
