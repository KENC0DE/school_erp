# scripts

Development tooling for the school ERP monorepo. Run everything from the repo
root. `./scripts/dev.sh help` prints the short usage.

## Standard commands

```bash
./scripts/dev.sh up       # compose (if Docker works) or SQLite fallback + both APIs/webs
./scripts/dev.sh seed     # idempotent demo data (refuses APP_ENV=production)
./scripts/dev.sh reset    # down, delete ./data, up, seed
./scripts/dev.sh test     # backend + controller + shared + boundary + JS tests, ruff, import-linter
./scripts/dev.sh mobile   # Expo on :8081 pointed at this machine's LAN IP
./scripts/dev.sh logs     # tail data/logs/*.log
./scripts/dev.sh down     # stop only the PIDs this launcher tracked
```

Windows PowerShell has the same subcommands: `.\scripts\dev.ps1 up`, etc.

Ports: school API **8000**, controller API **8100**, school web **5173**,
controller web **5174**, Postgres 5432, Redis 6379, MinIO 9000/9001, Mailpit
8025, Expo 8081.

## Database modes

- If a Docker daemon is reachable **and** `deploy/compose/dev.yml` exists, `up`
  starts Postgres (two databases), Redis, MinIO and Mailpit, applies Alembic
  revisions, then starts the apps against PostgreSQL.
- Otherwise it uses the documented SQLite fallback:
  `data/erp_demo.db` and `data/controller.db`. This is the mode used on build
  hosts without Docker. The app creates the schema on startup; no Alembic is
  required.
- `reset` only deletes paths inside `./data`. It never removes anything outside
  the repository.

Background processes are recorded in `data/dev.pids` (name, PID, port, process
start time). `down` verifies the start time and command line before killing a
PID, so a recycled PID is left alone. Vite/uvicorn children are stopped through
the tracked process tree only.

## Seed

`scripts/seed.py` writes both databases in-process (no server required). It is
an upsert pass; re-running is safe. It creates:

- Controller: `owner@controller.local` (owner), `support@controller.local`
  (support), school code `DEMO` ("Demo Academy", modules include `academics`
  and `sample`), signing keys, and one canonical enrollment token
  `dev-enroll-DEMO-2026` (printed once when created).
- School: all Phase 0 demo accounts from the build guide §1 (each assigned its
  documented role), every shipped default role plus the demo-only `limited`
  role, the shipped grade-level and stage catalog (KG 1–Grade 12, five stages,
  flagged as starter data), four school-layer Amharic translation overrides,
  the builtin theme plus two importable example themes (`highlands`, `sunset`),
  one sample note, one instance setting, and a controller-signed license. Role
  assignments, the limited role's permissions, translation overrides, imported
  themes, the setting and the note are written through the normal audited
  service paths, so a fresh instance has ready-made activity history.

The seed signs the license with the controller's own license key and applies it
with the normal license-verification path instead of calling
`POST /controller/v1/enroll`. That keeps seeding offline and deterministic; the
canonical enrollment token is left unused so the real HTTP enrollment flow can
still be exercised manually. The instance public key is also recorded on the
controller school record, so heartbeats work after seeding.

All demo accounts use password `DevPass#2026`. **Never use these in production.**

`dev.sh`/`dev.ps1` also export the development-only controller directory signing
key (`DIRECTORY_KID=k1`) whose public half is embedded in the mobile app. If a
controller database was seeded before this key existed, run
`./scripts/dev.sh reset` once so the controller adopts it; otherwise the mobile
school picker will reject the signed directory record as untrusted. Production
must set `DIRECTORY_PRIVATE_KEY` to a secret key and ship the matching public key
through `EXPO_PUBLIC_CONTROLLER_DIRECTORY_PUBLIC_KEY`.

## API client generation

```bash
./scripts/gen-api.sh            # CI check: regenerate and fail on a diff
./scripts/gen-api.sh --write    # update shared/ts/api-client/src/schema.d.ts
./scripts/gen-api.sh --controller  # optional: data/openapi/controller.json
```

The school OpenAPI document is produced from `create_app()` in-process, without
starting uvicorn. The controller document is optional and written under
`data/` (gitignored).

## API compatibility guard

`shared/openapi/v1.json` is the last released `/api/v1` contract. CI compares
the generated schema with it and fails on removed or renamed endpoints and
fields, narrowed types, and new required request fields or parameters:

```bash
uv run python scripts/check-api-compat.py           # CI check
uv run python scripts/check-api-compat.py --write   # release step: snapshot
```

Additive changes pass without touching the snapshot. `--write` rotates the old
snapshot to `shared/openapi/v1.previous.json`, which lets the checker enforce
the "deprecations stay for at least two releases" policy: a removed item must
be marked `deprecated: true` in both snapshots. Only run `--write` when cutting
a release, never to silence a breaking change in a feature branch.

## i18n check

`scripts/check-i18n.py` is offline and deterministic:

- every literal key used via `t("...")` (or `$t` / `i18n.t`) in the web and
  mobile sources must exist in the default English bundles;
- each `en.json` and `am.json` pair must have the same key set.

Module bundles are addressed with their namespace prefix (`sample.title` comes
from `modules/sample/i18n/en.json` key `title`).

## Boundaries

`scripts/check-boundaries.sh` wraps the Python import-linter contracts and the
workspace ESLint zone rules. It is wired into CI and is equivalent to the
pre-commit hooks.

## Python environment

`dev.sh` looks for an interpreter that can import FastAPI, SQLAlchemy, uvicorn
and aiosqlite, in this order: `$ERP_PYTHON`, `./.venv`, the two package venvs,
then `uv run --no-sync`. On a normal clone run `uv sync --all-packages` first.
`seed.py`, `gen-api.sh` and `check-i18n.py` work standalone with the same
resolution.

## Windows limits (dev.ps1)

`dev.ps1` is best-effort: it needs PowerShell 5.1+, an existing `uv`/`pnpm`
install and an interpreter with the backend dependencies (`ERP_PYTHON` can
point at it). Logs are split into `<name>.log` / `<name>.err`. Process-tree
cleanup uses `taskkill /T`. Expo is started in LAN mode; Docker fallback and
flags are the same as on Unix.
