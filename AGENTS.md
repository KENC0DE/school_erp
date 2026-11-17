# Agent instructions

## Autonomous build mode

This repository is being built from `docs/02_BUILD_GUIDE.md`, task by task, using
`docs/PROGRESS.md` as the checklist. Work autonomously:

1. Read `docs/PROGRESS.md` and take the **first unchecked task** (unless the user
   names a different task).
2. Read only the architecture sections that task cites in
   `docs/02_BUILD_GUIDE.md` / `docs/01_PROJECT_ARCHITECTURE.md`.
3. Implement the task and its tests. Never delete, skip or weaken a test to get
   green.
4. Run the task's **Verify** step plus the relevant full checks (backend tests,
   lint/format, typecheck, build, i18n, api-client diff, e2e when the change
   touches an exercised flow).
5. Update `.env.example` and `docs/DECISIONS.md` when the task changes
   configuration or leaves a judgement call.
6. Tick the task in `docs/PROGRESS.md` only after verification passes.
7. Commit with `P{phase}-{nn}: short description`.
8. Immediately continue with the next unchecked task.

Do **not** stop for per-task confirmation and do **not** ask "shall I continue?"
between tasks. Keep going until every task in `docs/PROGRESS.md` is checked, or
until a task is genuinely blocked by something only the user can provide (a
credential, physical device, paid service, or an ambiguous product decision).
For a true blocker: write it to `docs/QUESTIONS.md`, record the decision context
in `docs/DECISIONS.md` if useful, then continue with the next unblocked task
instead of idling.

After a context compaction or a new session, resume by running:

```sh
git log --oneline -5
git status --short
```

and re-reading `docs/PROGRESS.md`, then continue the loop above.

## Non-negotiable engineering rules

Follow `docs/02_BUILD_GUIDE.md` §0.2. In particular: one task at a time; tests
with every task; no hard-coded user-facing strings or colors; no floats for money
or marks; no hard deletes; every mutation audited through a service function;
every route declares a permission; additive-only `/api/v1`; module gating and
zone boundaries preserved; keep files small and focused.
