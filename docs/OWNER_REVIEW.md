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

## 2026-11-19 — Phase 4 assessment flow (owner script)

- **What:** the marks and grading module end to end — mark structures, grade
  bands, the web mark-entry grid, mobile entry with the offline outbox, the
  manager dashboard, approvals, published parent/student results, and the AI
  previews for entering marks and publishing.
- **How to look:** `./scripts/dev.sh up && ./scripts/dev.sh seed`, then sign in
  as the demo accounts (`DevPass#2026`):
  - `academichead@demo.school` — open **Assessment**; the seeded school
    structure totals 100 and the default scale has the custom C+ band (75–<85);
    the grade test tool shows `80 → C+`.
  - `teacher1@demo.school` — Grade 5 A Mathematics; open **Quiz 1** (out of 15)
    and **Quiz 2** (out of 13), enter marks, and watch the converted column
    (`12/15 → 8.00`, `10/13 → 7.69`). Submit the section's marks.
  - `academichead@demo.school` — approve, publish, then lock in **Approvals**.
  - `academichead@demo.school` — widen a band in **Grade rules**; live result
    labels change, the raw marks in the grid do not, and an already published
    snapshot keeps its original labels.
  - `teacher1@demo.school` — request a correction on a locked mark.
  - `parent1@demo.school` / `student1@demo.school` — the assessment page shows
    the published results view, and only published results.
- **Good:** entering marks for a 60-student section feels immediate; converted
  values agree with the structure; a parent never sees a draft, submitted or
  approved mark; raw marks survive every band and structure edit.
- **Automation:** the whole script also runs headless over the API in
  `school-erp/backend/tests/test_owner_script_assessment.py`. The two
  performance figures are produced by `scripts/bench_assessment.py` and
  recorded in `docs/DECISIONS.md`.
- **Checked against:** `docs/UI_CHECKLIST.md` for the new assessment screens;
  the Playwright mark-entry test (`e2e/tests/marks.spec.ts`) enters 30 marks with
  the keyboard and a pasted column.
