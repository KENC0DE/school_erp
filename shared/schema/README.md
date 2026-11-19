# Shared schemas

Committed, generated or hand-authored artifacts that both the TypeScript and
Python sides must agree on.

| File | Source | Checked by |
| --- | --- | --- |
| `document-layout.v1.json` | Generated from `shared/ts/documents/src/layout.ts` | `shared/ts/documents/tests/layout.test.ts`, `school-erp/backend/tests/test_document_layout.py` |
| `document-layout.fixtures.json` | Hand-authored conformance corpus | Both suites above |

Regenerate the layout schema after editing the Zod definition:

```sh
pnpm gen:documents        # node shared/ts/documents/scripts/gen-schema.ts --write
```

`node shared/ts/documents/scripts/gen-schema.ts` without `--write` exits
non-zero when the committed file is stale, so it can gate a change. The fixture
corpus is deliberately shared: a refinement added to Zod but not to Pydantic
(for example the custom page-size rule) makes one suite fail on the same
fixture instead of drifting silently.
