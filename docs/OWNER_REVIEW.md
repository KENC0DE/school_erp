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
