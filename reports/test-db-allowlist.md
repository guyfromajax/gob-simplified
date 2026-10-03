# Test DB guard: deny-list → allow-list

Branch `feature/test-db-allowlist`, cut off develop `9f07d5650`.
(The brief named `e4ff0d78e`; develop had moved on by two commits. Nothing in the delta touches tests or db config.)

**What changed:** `_BLOCKED_DB_NAMES = frozenset({"gob", "gob-staging"})` — duplicated in both conftests — is gone. One shared module, `tests/db_guard.py`, now decides, and it is an allow-list: an unrecognised name aborts.

---

## 1. DB-name inventory, and the pattern

Every database name that appears anywhere in the repo, its configs or its scripts:

| Name | Where | Real or mock | Allowed? | Why |
|---|---|---|---|---|
| `gob` | production `ENVIRONMENT=production` (`env_config.py:191-199`) | real | **no** | production |
| `gob-staging` | `.env.local`, `.env.example`, `development`/`staging` | real | **no** | emptied 4× in ~1 month |
| `gob-test` | both conftests' `setdefault`; what CI runs on | either | **yes** | the disposable default |
| `gob-scratch-test` | `tests/test_script_db.py:267` | real | **yes** | explicitly a scratch test DB |
| `gob-s11-league-convergence` | `scripts/s11_provision_convergence_scratch.py:27` | real | **no** | script-only; never a pytest session DB, so allowing it buys nothing |
| `gob-remote-memory` | `persistence/sqlite.py:271` | **real remote client** | **no** | a real connection with a name that reads disposable — exactly the case a deny-list misses |
| `gob-eog-memory` | `persistence/sqlite.py:282` | explicit mongomock | n/a | allowed via the mock branch, not the name |
| `scratch-test` | mongomock target inside a test | mock | **no** (by name) | no `gob-` prefix; allowed via the mock branch |

Not DB names, excluded as false positives: `gob-api-cache*`, `gob-loopback`, `gob-frontend`, `gob-backend`.

```
ALLOWED_DB_NAME_PATTERN = r"^gob-(?:test|scratch-test)(?:-[A-Za-z0-9._-]+)?$"
```

- `startswith("gob-test")` would have **missed `gob-scratch-test`** — hence the alternation, not a prefix.
- Optional suffix admits per-worker DBs (`gob-test-w1`) without widening to anything not already a test DB.
- Anchored both ends. `agob-test` and `gob-test-` … `evil` style near-misses are tested explicitly (§3).
- Ambiguous names were left **disallowed**, per the brief. `gob-s11-league-convergence` is the one that was tempting; it is a script's DB and the escape hatch covers it if anyone ever needs it under pytest.

## 2. Mock detection — the signal, and why it is trustworthy

```python
type(obj).__module__.split(".")[0] == "mongomock"
```

Checked on the **live handle the tests will use**, then on its `client`, then through a bounded (depth 4) unwrap of `_database/_db/_wrapped/_delegate/_collection/_client` so a proxied mock still reads as in-memory.

| Candidate signal | Rejected because |
|---|---|
| `GOB_DB_MODE` | It is an *input* that selects which store to build — the thing the brief says not to depend on. Stale or mistaken is precisely how this goes wrong. |
| `USING_MONGOMOCK` | Set as `db_env.db_mode == "mongomock"` (`persistence/mongo.py:96`) — the same env var renamed. |
| The DB name | A label anyone can set. That is what stage 2 is for. |

Verified live: under the repo default the handle is `mongomock.database.Database` / `mongomock.mongo_client.MongoClient`, **including under `GOB_DB_ACCESS=read`** (the read-only proxy does not hide it). A type cannot be spoofed by a name or an env var: if it's a mongomock object, writes land in a dict in this process and vanish at exit.

Order matters and is deliberate: **mock first**. A mongomock store cannot lose anyone's data, so aborting on its name would be a pure false positive.

## 3. The guard's own tests — each demonstrated failing first

`tests/test_db_guard.py`, 13 tests. The four the brief required, plus nine that pin the edges:

| Test | Pins |
|---|---|
| `test_aborts_on_a_real_connection_with_a_disallowed_name` | required case 1 |
| `test_allows_a_mock_store_even_with_a_disallowed_name` | required case 2 |
| `test_allows_a_real_connection_with_an_allowed_name` | required case 3 |
| `test_the_escape_hatch_works_and_is_off_by_default` | required case 4 |
| `test_the_pattern_does_not_admit_near_misses` | `gob`, `gob-staging`, `gob-remote-memory`, `gob2`, `gobtest` |
| `test_the_pattern_is_anchored_at_both_ends` | prefix/suffix smuggling |
| `test_mock_detection_cannot_be_spoofed_by_a_name` | a real object named `gob-test-…` is still judged on type |
| `test_mock_detection_does_not_read_the_environment` | verdict unchanged with `GOB_DB_MODE` set either way |
| `test_a_wrapped_mock_is_still_recognised` | the read-only proxy case |
| `test_a_mock_client_alone_is_enough` | db handle without a mock module root |
| `test_detection_terminates_on_a_self_referential_proxy` | the guard can't become its own outage |
| `test_the_refusal_message_says_how_to_proceed` | message names the pattern and the hatch |
| `test_no_db_at_all_is_refused_not_allowed` | `None` is not a free pass |

**Poison tests — all four caught** (the tests fail when the guard is broken, which is what makes them worth having):

| Poison | Failures |
|---|---|
| revert to the deny-list | 4 |
| infer mock-ness from `GOB_DB_MODE` | 1 |
| widen the pattern to `^gob-` | 2 |
| escape hatch defaulting ON | 6 |

**End-to-end, against real connections** (not just unit tests):

| Scenario | Result |
|---|---|
| real `gob-staging` | `❌ Refusing to run pytest (tests/)` |
| real `gob-remote-memory` | refused |
| real `gob2` (one-char typo of production — **the old deny-list permitted this**) | refused |
| real `gob-staging` + `GOB_ALLOW_DESTRUCTIVE_TESTS=1` | `⚠️ … running against the REAL database 'gob-staging' (tests/)`, run proceeds |
| real `gob-test`, `ENVIRONMENT=test` | allowed by the guard, then failed on a genuine connection error — proving the allowed-name branch is reachable, not dead |

## 4. Escape hatch

```
GOB_ALLOW_DESTRUCTIVE_TESTS=1 pytest ...
```

- Off by default; only the exact string `1` enables it.
- Checked **after** the name allow-list, so it is never load-bearing for a normal run.
- Prints a loud `⚠️` banner naming the real database and the tree. A destructive run against a real DB is never quiet.

## 5. Gates

| Gate | Result |
|---|---|
| `pytest` (repo root) | **3664 passed**, 20 skipped, 110 xfailed |
| `pytest tests/` | **3421 passed**, 20 skipped, 110 xfailed |
| `pytest BackEnd/tests/` | **243 passed** |
| single file inside `BackEnd/tests/` (the IDE-gutter-click case that originally bypassed the guard) | 8 passed, **still guarded** |
| equiv-v3, 240 cells | **240/240**, fp+draws **480/480**, 0 mismatches |
| anchor seed 8000 played SD=1 | fp `0c3389cd41d0bbef`, draws `75363` ✓ |

Rule 6e footing (equiv-v3 row only): worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process, `GOB_DEFENDER_AG_SPREAD` unset (= ON). 160 cells vs `equiv_v3_reference_f600628a4_agspread.json` + 80 vs `equiv_v3_loose_baseline_f600628a4_agspread.json`.

Movement: none. This branch touches no sim code — only conftests and a new test-only module.

> The 3421 for `tests/` is **lower** than the ~3651–3712 seen on other recent branches. That is not a regression: this branch is off a different develop tip and does not carry the flag-registry / depth-ordering test additions. Root + BackEnd + tests reconcile exactly: 3421 + 243 = 3664.

## 6. Tunable Constants

| Constant | Location | Value | Effect |
|---|---|---|---|
| `ALLOWED_DB_NAME_PATTERN` | `tests/db_guard.py` | `^gob-(?:test\|scratch-test)(?:-[A-Za-z0-9._-]+)?$` | Which real DB names a destructive suite may use. Widening it widens the blast radius. |
| `ESCAPE_HATCH_ENV` | `tests/db_guard.py` | `GOB_ALLOW_DESTRUCTIVE_TESTS` | Env var name for the deliberate opt-in. Only `"1"` enables. |
| `_MOCK_ROOT` | `tests/db_guard.py` | `mongomock` | Root package whose objects count as in-memory. |
| `_UNWRAP_ATTRS` | `tests/db_guard.py` | `_database, _db, _wrapped, _delegate, _collection, _client` | Wrapper attributes unwrapped when looking for a mock behind a proxy. |
| unwrap depth | `is_in_memory_store` | `4` | Recursion bound. Prevents a self-referential proxy hanging the guard. |

## 7. Unverified, and things found on the way

- **The brief's motivating scenario is already unreachable.** `BackEnd/env_config.py:143-146` raises `"Mongomock database name must not be gob or gob-staging"`, and `:191-199` pins `ENVIRONMENT` → `MONGO_DB_NAME`. So the specific "`.env.local` points at gob-staging under mongomock" path was already closed. The allow-list still matters: it is the *real-connection* names — `gob2`, `gob-remote-memory`, anything new — that `env_config` does not cover and the deny-list let through.
- **Not done, per scope:** the dozen-plus files calling `delete_many({})` are untouched; no test assertion changed; `GOB_DB_MODE` / `GOB_DB_ACCESS` / `GOB_PERSISTENCE` defaults untouched (they are in `PROTECTED_DOTENV_KEYS`, `env_config.py:21`); `.env.local` and `.env.example` untouched.
- **Reported, not fixed** (the brief asked for this specifically): `GOB_PERSISTENCE` is read at three sites with **two different defaults**.
  - `env_config.py:82` — the authoritative one — reads a *pristine* pre-dotenv snapshot and defaults to `"mongo"`.
  - `api/_bootstrap.py:60` and `loopback_app.py:50` read live `os.environ` and default to `"sqlite"`.

  Both of the `"sqlite"`-defaulting reads are health-payload **reporting** inside an `is_loopback()` branch, so with the var unset a loopback `/health` can report `sqlite` while the resolved store is `mongo`. It does **not** change which store the guard sees: the guard reads the live `BackEnd.db` handle, built once from the `env_config` resolution. Reported, not fixed here.
- **Not tested:** parallel/xdist per-worker DBs. The pattern admits `gob-test-w1`, but nothing in this repo currently creates one, so that arm of the pattern is unexercised in practice.
