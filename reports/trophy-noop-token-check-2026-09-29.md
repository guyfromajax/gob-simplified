# Trophy no-op and UI token check — 2026-09-29

Branch `chore/trophy-noop-and-token-check` (from `origin/develop`).

## A — week-35 All-American writes

### Approach

`_persist_week_35_awards_if_needed` still runs on every command-center read at week 35+. It now calls `record_all_american_trophies_if_missing` instead of `record_all_american_trophies`.

That helper builds the expected `trophy_keys` map keys for the user-team All-Americans (same key `append_trophy` stores, with `.` and `$` replaced). It then does one `find_one` of the coach doc with projection `{"trophy_keys": 1, "_id": 0}` — the map only, not the rest of the user or `local_coach` doc. When every expected key is already present, it returns without calling `append_trophy`. When any key is missing, it records through the existing guarded update, so a replay still cannot duplicate an entry.

The other option was to record only when the awards are first computed, plus a one-time catch-up flag on the franchise. That is cheaper on the steady path (no read at all), and it is not as safe. The coach key map is the only place that knows whether each All-American was logged. A flag on the franchise can diverge from it: the online user doc may not exist yet, a partial append can fail, or a desktop save can be copied without the flag. The projected read uses the same map as the idempotency guard, so a save whose awards were computed before the trophy log still catches up exactly once, and every later Office load does not write.

Nothing in the sim, `cpu_week_pool`, `sim_rng`, or finalize changed.

### Write counts

Five command-center reads (`command_center_data`) at week 35, awards already stored (`computed_at` left as `before-trophy-log`, so this is the pre-merge save, not a fresh compute). Two user-team All-Americans and two CPU All-Americans. Counts are from a spy on the coach collection's `update_one`, and on the desktop SQLite save from the connection's statement trace. Not from reading the trophy list back.

Guarded `trophy_keys` updates (one `$set` of `trophy_keys.<key>` per All-American):

| Store | Owner | Before (per read) | After (per read) |
|---|---|---|---|
| mongomock | local coach | 2, 2, 2, 2, 2 | 2, 0, 0, 0, 0 |
| mongomock | online user | 2, 2, 2, 2, 2 | 2, 0, 0, 0, 0 |
| SQLite | local coach | 2, 2, 2, 2, 2 | 2, 0, 0, 0, 0 |

Across the five reads that is 10 guarded updates before and 2 after: one write per All-American, on the first read only.

The local coach's `append_trophy` also issues a `$setOnInsert` upsert before each guarded update. That is unchanged, and it now runs only on the catch-up:

| | Before, all `update_one` calls per read | After |
|---|---|---|
| local coach (mongomock and SQLite) | 4, 4, 4, 4, 4 | 4, 0, 0, 0, 0 |
| online user | 2, 2, 2, 2, 2 | 2, 0, 0, 0, 0 |

SQLite `save_meta` write statements (`INSERT` / `UPDATE` / `REPLACE` / `DELETE`) on the same five reads: before `7, 4, 4, 4, 4`, after `7, 0, 0, 0, 0`. The four that repeated on every later load were the two upserts and the two guarded appends. They are gone after the catch-up. The first read stays at 7 because that catch-up still writes once, and the first Office load also does three other `save_meta` writes that were already there before this change.

Each of the five reads does exactly one projected `trophy_keys` find. Reads 2–5 do not call `update_one` on the coach doc.

`tests/test_trophy_log.py::test_command_center_week_35_reads_write_each_all_american_once` covers mongomock and SQLite, local and online. The SQLite statement trace is asserted for the local coach, which is the save file. (Outside tests the SQLite profile refuses the remote `users` collection; the test profile keeps that collection as in-memory mongomock, so an online owner on the SQLite store is still counted with the spy.)

## B — token check

Report only. No CSS was changed.

```
python scripts/check_ui_tokens.py
python scripts/check_ui_tokens.py --strict
```

Run from the repo root. Standard library only, no network. The default exits 0 and writes `reports/ui-token-audit-2026-09-29.md`. `--strict` exits 1 when any colour-law hit exists, for a later merge gate.

Scans `FrontEnd/static/**/*.css` (except `css/gob-tokens.css`), `<style>` blocks and `style=""` attributes in HTML, and JS that builds inline styles. Near-duplicates are grouped by hue with the brand token (`--green`, `--orange`, `--navy`, `--blue`, `--red`, `--yellow` for gold). White and grey report distance to the nearest ramp stop, including alpha.

New vs legacy: shell HTML (`gob-shell` / `gob-focus`, or a page in `gobShell.js` `PAGES`), `css/gob-*.css`, `css/office-home.css`, `js/shared/gob*.js`, and `js/shared/views/**` are new. Everything else is legacy.

### Headline numbers (this tree)

| Category | Count |
|---|---|
| green | 428 |
| orange | 747 |
| navy | 265 |
| blue | 153 |
| red | 241 |
| white/grey | 4166 |
| gold | 401 |
| other | 4 |
| colour total | 6405 |
| font-size | 2304 |
| font-weight | 1330 |
| letter-spacing | 1012 |
| font-family | 1058 |
| type total | 5704 |

Colour-law (`--reward-gold` is unused: 0 hits):

| Surface | Green | Orange | Total |
|---|---|---|---|
| new | 22 | 55 | 77 |
| legacy | 418 | 873 | 1291 |
| total | 440 | 928 | 1368 |

Top files by colours + type + colour-law hits. All twenty are legacy:

| File | Colours | Type | Law |
|---|---|---|---|
| franchise-command-center.css | 556 | 401 | 67 |
| court.html | 463 | 265 | 93 |
| team-builder.css | 290 | 350 | 32 |
| recruiting-spine.css | 159 | 396 | 59 |
| recruiting-signing.css | 154 | 318 | 76 |
| mode-select.css | 265 | 170 | 52 |
| training.css | 244 | 121 | 51 |
| training-report.css | 161 | 151 | 22 |
| set-lineup.css | 179 | 115 | 29 |
| recruiting.css | 139 | 106 | 41 |

The new-surface law hits are real uses, not the Advance button: `var(--green)` on column dots, risk tags, chemistry, and attitude bars; `var(--orange)` on callouts and meters. Detail is in the audit report.

## Merge gate

`pytest --ignore=tests/e2e`: 3923 passed, 20 skipped, 109 xfailed, 1 xpassed, 0 failed (192.59s).

Playwright `tests/e2e --workers=1` on port 8157 with `CI` unset, and no other Playwright run in progress: 547 passed, 3 skipped, 0 failed (8.1m).

STATUS: COMPLETE
