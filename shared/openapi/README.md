# OpenAPI release snapshots

`v1.json` is the `/api/v1` contract of the last release, generated from
`create_app().openapi()` without starting a server. CI and the backend test
suite compare the current schema against it with
`shared/py/erp_shared/api_compat.py`.

- Additive changes pass and need no update here.
- Breaking changes fail the guard. Use `/api/v2` or deprecate the item instead.
- `v1.previous.json` is the release before the current baseline. The
  compatibility checker allows a removal only when the item was
  `deprecated: true` in **both** files, enforcing a two-release deprecation
  window.

At release time only:

```bash
uv run python scripts/check-api-compat.py --write
```

That command rotates `v1.json` to `v1.previous.json` and writes the new
baseline. Never run it in a feature branch to make the guard pass.
