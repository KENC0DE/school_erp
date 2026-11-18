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
