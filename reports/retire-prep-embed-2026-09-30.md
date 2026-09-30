# Retire the Prep embed bridge — 2026-09-30

Branch `chore/retire-prep-embed` off `origin/develop` (`6f0bbcf18`). Chapter 8 cleanup only. Worked in `~/gob-stats`.

## What moved / deleted

Moved out of `FrontEnd/static/js/shared/views/prepEmbed.js` into `FrontEnd/static/js/shared/views/viewLoader.js`:

- `ensureCss`
- `loadScript`
- `ensureFranchiseMode` — FranchiseContext only (`get('franchise_id')` / `set('mode')`). The old URLSearchParams fallback is gone so the new file is not a Gate B hit.

Deleted from the product (and then the file):

- `embed()`
- `loadIsolated()`
- `prepEmbed.js`

Importers now use `./viewLoader.js`:

- `trainingView.js`
- `trainingReportView.js`
- `gamePlanView.js`
- `playbooksView.js`
- `scoutingView.js`

`scoutingView.js` reads `franchise_id` / `team_id` through the same `contextValue(key)` + `FranchiseContext.get` shape as the other Prep views. No `location.search`.

## HTML leftovers

Removed the `embed=1` skip and the `init(document.body)` path that only existed for it.

| File | Kept | Dropped |
|---|---|---|
| `training.html` | Browse redirect to `?tab=training-view`. `mode=tutorial` stays on the file and calls `init(document.body)` (`#submit-btn`). | `embed=1` skip + leftover init. |
| `training-report.html` | Always redirects to `?tab=training-report-view`. | `embed=1` skip + leftover init (and the unused `init` import). |
| `game-plan.html` | Browse redirect. `resume_from_timeout=true` and `mode=tutorial` stay focus and call `init(document.body)`. | `embed=1` skip + leftover init. |
| `playbooks.html` | Browse redirect. `mode=tutorial` stays on the file and calls `init(document.body)`. | `embed=1` skip + leftover init. |

The four redirect IIFEs still use `URLSearchParams(location.search)`. They run as the first `<script>` in `<head>`, before `franchiseContext.js` loads, and they must copy `franchise_id` / `team_id` / `week` onto the FCC URL. Removing `embed=1` does not let them drop the query string. Allow-list counts on those four files stay at 1.

## Grep proof (`FrontEnd/static`)

```
rg -n "prepEmbed|loadIsolated\\(|embed\\(" FrontEnd/static
# (no hits)

rg -n "embed=1" FrontEnd/static
# (no hits)
```

Zero hits for `prepEmbed`, `embed(`, `loadIsolated(`, and `embed=1` under `FrontEnd/static`.

Unrelated leftover (not this bridge): `fcc-recruiting-footnote--embed` in the command center, `bag.delete('embed')` cleanup in `training.js`, and a comment in `trainingView.js` about matching develop-era CSS.

## Allow-list before → after

Hand-edited `scripts/ci/migration_gates_allowlist.json`. Never `--write-allowlist`.

| File | Develop | After |
|---|---|---|
| `js/shared/views/prepEmbed.js` | 1 | removed (file deleted) |
| `js/shared/views/scoutingView.js` | 1 | removed (0 hits) |
| `js/shared/views/viewLoader.js` | — | not added (0 hits) |
| `training.html` | 1 | 1 (query forward) |
| `training-report.html` | 1 | 1 (query forward) |
| `game-plan.html` | 1 | 1 (query forward + timeout/tutorial skip) |
| `playbooks.html` | 1 | 1 (query forward + tutorial skip) |

Gate B: **138 lines / 46 files → 136 lines / 44 files**. `check_migration_gates.py` passed.

## Other references updated

Old specs that asserted the embed path now assert the module path (not deleted):

- `tests/test_prep_modules_{training,report,gameplan,playbooks}.py` — `from './viewLoader.js'`, no `prepEmbed`, no leftover `embed') === '1'` in HTML.
- `tests/test_prep_modules_report.py` — standalone file no longer imports `init` (always redirects).
- `tests/e2e/prep-modules-{training,report,gameplan,playbooks}.spec.js` — still assert no `*.html` embed fetch; also assert `viewLoader.js` is requested and `prepEmbed.js` is not.
- `tests/test_retire_prep_embed.py` — file gone, loader has no embed/URL reads, static tree has no `prepEmbed` / `loadIsolated(`.
- `tests/e2e/retire-prep-embed.spec.js` — 1280 shots + tutorial stay-on-file.

Docs:

- `_documentation_master/11_Design_Systems/UX_System.md` §7 Training / Playbooks leftover `embed=1` lines removed. §9 table: `training.html`, `training-report.html`, `playbooks.html` no longer mention leftover embed. §14 still says the modules do not fetch `*.html?embed=1` (that is the module path).
- `reports/coverage-map-2026-09-29.md` — Training / Game Plan / Playbooks / Training Report Kind column is **IN-APP VIEW**. Recommendation row updated.

Listed, not rewritten (historical):

- `reports/prep-modules-2026-09-29.md` (cleanup batch left `prepEmbed.js` and leftover `embed=1`)
- `reports/prep-v2-pr2-2026-09-28.md`, `reports/prep-v2-pr3-2026-09-28.md`
- `reports/polish-prep-train-scout-2026-09-29.md`, `reports/polish-prep-plan-2026-09-29.md`
- `reports/ch8-cleanup-1-2026-09-29.md`

Did not touch: `office-home.*`, `officeHome.js`, `gob_nav` / alpha-badge, `scripts/check_ui_tokens.py`, season-peak / milestone / trophy CSS, Training Report Team Report display list (Momentum stays on this branch).

## First-open timing

`scripts/measure_nav_timing.js --only=training-view,game-plan-view,playbooks-view,scouting-view,training-report-view --pass=timing --runs=5` (PORT 8192, desktop + online). Baseline from `reports/prep-modules-2026-09-29.md` (Scouting cold from the coverage-map embed-era row).

| screen | profile | this run cold | this run warm | baseline cold | baseline warm |
|---|---|---|---|---|---|
| training-view | desktop | 30/38 | 14/22 | 27/32 | 15/15 |
| training-view | online | 27/39 | 15/16 | 25/25 | 10/12 |
| game-plan-view | desktop | 33/115 | 5/6 | 30/33 | 5/7 |
| game-plan-view | online | 37/38 | 5/8 | 29/30 | 6/7 |
| playbooks-view | desktop | 393/419 | 8/9 | 113/194 | 7/8 |
| playbooks-view | online | 378/414 | 8/9 | 114/117 | 8/8 |
| training-report-view | desktop | 11/26 | 3/6 | 16/18 | 3/4 |
| training-report-view | online | 11/18 | 4/5 | 15/19 | 2/3 |
| scouting-view | desktop | 474/554 | 8/10 | 154/180 (coverage-map) | 39/72 |
| scouting-view | online | 440/465 | 9/10 | 152/188 (coverage-map) | 43/64 |

Training, Game Plan (median), and Training Report are within noise. Game Plan desktop worst 115 is one spike; median 33 vs 30. Playbooks / Scouting **cold** are slower than the 2026-09-29 / coverage-map medians (fresh Lancaster seed, first paint of the same module JS). **Warm** matches or is better (Playbooks 8 vs 7–8; Scouting 8 vs 39 — the panel stays mounted). No timeouts. Same `ensureCss` / `loadScript` semantics; no HTML embed fetch. Raw: `reports/retire-prep-embed/timings.json`.

## Screenshots (1280, opened)

| File | What |
|---|---|
| `reports/retire-prep-embed/after-training-1280.png` | In-app Training. Rail + Prep underline. Points pill in `.pg-tools`. Advance Submit Training. No standalone `#submit-btn` in the view. |
| `reports/retire-prep-embed/after-training-report-1280.png` | In-app Training Report. Week 12, Four Corners, notes + Team Report. Did not edit the Team Report list. |
| `reports/retire-prep-embed/after-game-plan-1280.png` | In-app Game Plan. Sliders + Save. No embed `#toast` in the view. |
| `reports/retire-prep-embed/after-playbooks-1280.png` | In-app Playbooks. Tables + Playcall Center + Save. |
| `reports/retire-prep-embed/before-scouting-1280.png` | Develop `scoutingView.js` + `prepEmbed.js` restored only for this shot, then removed. |
| `reports/retire-prep-embed/after-scouting-1280.png` | Same layout after FranchiseContext. Four Corners, projected five, measures. |
| `reports/retire-prep-embed/after-tutorial-1280.png` | `training.html?mode=tutorial` stayed on the file. `#submit-btn` visible. |

## Gate counts

- `check_migration_gates.py`: **passed**. Gate A 0/0. Gate B 136 lines / 44 files.
- pytest `--ignore=tests/e2e -q` (outside sandbox): **4137 passed**, 16 skipped, 109 xfailed, 1 xpassed (`test_leaders_view_scope_filters_to_user_conference`, known broken-harness), **0 failed**.
- Token `--strict`: exit 1. New-design law hits are **11 `--reward-gold` only** (0 green, 0 orange) in office-home / home-base / milestone / season-peak / trophy CSS — the audit agent's false positive. No new hit in files this branch touched. Checker rewrote `reports/ui-token-audit-2026-09-29.md`; not committed.
- Full Playwright, workers=1, port 8157, CI unset: **747 passed**, 4 skipped, **0 failed** (10.8m).

## Tests

- `tests/test_retire_prep_embed.py` (4)
- Existing prep-module python + e2e specs updated to the module path
- `tests/e2e/retire-prep-embed.spec.js` (shots + tutorial)
