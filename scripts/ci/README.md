# Migration gates

CI ratchets that freeze the desktop-migration pile so it can only shrink.

| Gate | What it freezes | Instead |
|---|---|---|
| A | New `BackEnd.db` collection-handle imports (WS-1) | persistence adapter |
| B | New `URLSearchParams` / `location.search` / `.searchParams` in `FrontEnd/static` (WS-3) | FranchiseContext |

`tests/`, `scripts/`, `scratch_*.py`, and `reports/` are out of scope.

## How to update the allowlist

`migration_gates_allowlist.json` is generated from the tree. Counts may fall, never rise.

After you delete a real import or URL-state read and the checker prints a `NOTE`:

```
python scripts/ci/check_migration_gates.py --write-allowlist
```

Commit the JSON together with the cleanup. Do not regenerate it to hide a new site.
