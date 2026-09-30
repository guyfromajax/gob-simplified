# Prep Scouting speed + SFX follow-ups

Branch `ux/prep-scouting-speed-sfx` in `~/gob-stats`, from `origin/develop`.

## 1. play-next-game side-effect finding

**Do not change the route.** `POST /franchise/play-next-game` is not side-effect free.

Handler: `BackEnd/api/franchise_routes.py` `play_next_game` (5688–5793).

- Ownership check + schedule/week read: 5688–5707.
- EOS weeks 27–34 (`eos_tournament_active` and tournament state present): calls `_maybe_reconcile_region_for_eos(..., context_label="play_next_game")` at 5716–5725.
- Regular season weeks 1–26: reads `schedule[week-1]`, looks up team names, returns the matchup. No `save_result`, no week increment (5766–5789).
- Returns the matchup JSON. No write in the regular-season branch.

`_maybe_reconcile_region_for_eos` (6838–6892) **does write** when it is a region week and reconciliation changes the bracket:

- Mutates `franchise_doc["region_tournaments"]` (6879).
- Persists: `db.franchises.update_one(..., {"$set": {"region_tournaments": updated_rt}})` (6880–6883).
- Logs `[EOS-REGION-RECONCILE]` (6884–6891).
- Returns `True` iff a write happened.

Scouting can be available in weeks 27–34 if the user is not eliminated (`resolveUpcomingOpponentFromMatchup` scoutingAvailable). Opening Scouting used to hit this POST, so it could persist region brackets. **The backend handler was left unchanged.**

Scouting now reads the opponent already on the loaded FCC payload:

- `commandCenterTopDataCache.next_game_summary` (`opponent_team_name` / `opponent_team_id`)
- else `office_digest.next_game` (`opponent` / `opponent_team_id`)
- cached per `franchiseId:week` for the page life (`upcomingOpponentByKey`)

`GOBFccPrep.peekUpcomingOpponent` exposes the cache/digest without a network call. Training no longer prefetches the scouting report (see §2c).

`_find_user_next_game` (used to build `next_game_summary` on `/franchise/command-center/data`) does **not** call the reconcile helper. Command-center load remains the place that already has the next opponent for regular season and EOS slates.

## 2. Before / after waterfall

Same seed path as `reports/perf-prep-cold-open/scout-waterfall.js`: Office → Prep/Training → Scouting sub-tab. Click → `#scouting-view .opp-n`. 5 cold contexts each, desktop + online. Script: `reports/prep-scouting-speed-sfx/measure-waterfall.js`.

The first “after” table used Playwright `waitForSelector` after `locator.click()`. Those numbers sat on an ~800ms floor even when the click path made zero requests. That clock is wrong (see §2b). Official times below are **in-page**: native click + `requestAnimationFrame` until `#scouting-view .opp-n` exists.

**Before** (Playwright clock, serial POST then team-data + scouting-report):

| Profile | painted ms (5 runs) | mean | Waterfall |
|---|---|---|---|
| desktop | 800, 800, 807, 806, 799 | 802 | POST `/franchise/play-next-game` at 28–200ms, then both GETs together ~246–303ms |
| online | 828, 802, 800, 800, 804 | 807 | same shape (POST then parallel GETs) |

**After (in-page clock, no Training prefetch, no play-next-game):**

| Profile | painted ms (5 runs) | mean | Waterfall after click |
|---|---|---|---|
| desktop | 476, 386, 416, 434, 359 | 414 | GET `team-data` + `scouting-report` together at 56–93ms |
| online | 363, 481, 431, 423, 389 | 417 | same |

**Warm-cache** (`WARM=1`, report already in `__gobScoutingReportCache`): 16–20ms both profiles (10/10). `performance.mark` sequence: `scouting-cache-hit` at 3ms → `scouting-paint-done` at 4–5ms. Under the ~300ms warm-cache target.

Screenshots 1280: `reports/prep-scouting-speed-sfx/scouting-before-1280.png` and `scouting-after-1280.png` (same opponent header / layout). JSON: `waterfall-before.json`, `waterfall-prefetch.json`, `waterfall-noprefetch.json`, `waterfall-warm.json`, `waterfall-trace.json`.

## 2b. The 800ms floor

**Exact wait:** `reports/prep-scouting-speed-sfx/measure-waterfall.js` — the old `page.locator(...).click()` + `page.waitForSelector('#scouting-view .opp-n', { state: 'attached' })` pair.

Not a product timer. There is no `setTimeout(800)`, no `transitionend` / `animationend` gate, no skeleton minimum-display, no `requestIdleCallback`, no font-load wait on this path.

- `gobViews.js` `skeleton` (93–99) / `show` (130–169): shared by every module view (rankings, training, game-plan, playbooks, scouting, …). `show` returns at 2–3ms on this click (`scouting-mount` at 2ms). Not the floor. Left unchanged.
- `gobTutorialNav.js:281` `setTimeout(clearEntering, 800)`: tutorial overlay entrance only. Not Scouting.
- `--dur-skeleton: 1.4s` in `gob-tokens.css`: CSS shimmer loop, not a JS min-display.
- `gobSubtabs.js` `fonts.ready`: layout fit only.

**Why Playwright sat at ~800ms:** the sub-tab click does `history.replaceState`. Playwright treats that as a navigation and `waitForSelector` after `locator.click()` waits out in-flight network (prefetch leftovers). Uniform 799–864ms because it was waiting for those fetches to finish, not for `.opp-n`. In-page `querySelector` sees `.opp-n` at the real paint time (~330ms with prefetch leftover, ~415ms without). After the node exists, a later `waitForSelector({ state: 'attached' })` returns in 5–17ms.

**Real remaining work on the product path** (not a delay): `scoutingView.js` `load()` (~559) → `fetchReport` / `prefetchOpponentReport` (144–169). Marks: `scouting-inflight-join` or `scouting-fetch-start` at 2–92ms, `scouting-data` when both GETs resolve, then `scouting-paint-start` / `scouting-paint-done` in the same turn. Scouting-only cache/inflight — kept (used by Scouting itself). No scouting-only sleep to remove.

## 2c. Training → Scouting prefetch A/B (then removed)

In-page clock, click as soon as Training sliders are visible. 5 desktop + 5 online.

| | desktop mean | online mean | overall |
|---|---|---|---|
| With prefetch | 319 (278–357) | 343 (287–389) | 331 |
| Without prefetch | 414 (359–476) | 417 (363–481) | 416 |

Saving: **~85ms** overall (95ms desktop, 75ms online). Under the ~100ms keep bar. **Removed** `prefetchScoutingOpen` from `trainingView.js` so Training open does not start `scouting-report` / `team-data` / scouting module import.

Prefetch was also late: it waited on `GOBFccPrep.whenReady()`, which is the same gate as “Training sliders visible”, so the GETs were still in flight at click (`scouting-inflight-join` every prefetch run). Without prefetch, click starts the two GETs together and `show` waits ~60ms for the scouting module import (`show-done` 54–92ms vs 2ms when the module was already imported).

## 3. SFX swap table

Catalog: `SFX_SELECT` = click-tiny.wav, `SFX_COMMIT` = click-beep.wav, `SFX_ADVANCE` only via `#play-now` `data-sfx`. No files added or renamed under `FrontEnd/static/sounds/`.

| Screen | Control | Was | Now |
|---|---|---|---|
| Training | sliders, tabs, auto-train, coaching radios, modal close, playbook-mode, req nudge | `click-tiny.wav` / `chaotic-choice.wav` / `whistle-3.mp3` / `positive-slide.wav` / `positive-plop.wav` / `positive-beep.wav` | `SFX_SELECT` |
| Training | custom-focus Assign | `confirm-1-lowervol.wav` (Advance file) | `SFX_COMMIT` |
| Training | Submit Training / `#play-now` | `confirm-2-lowervol.wav` **plus** `#play-now` `data-sfx=SFX_ADVANCE` | handler silent; Advance only via `#play-now` `data-sfx` |
| Game Plan | slider change | `click-tiny.wav` | `SFX_SELECT` |
| Game Plan | Save button / legacy unsaved overlay Save | `confirm-2-lowervol.wav` | `SFX_COMMIT` (not inside `saveGamePlan`) |
| Game Plan | back to command center | `x-back.mp3` | `SFX_SELECT` |
| Game Plan | tutorial PLAY NOW | `playAdvance()` | `data-sfx="SFX_COMMIT"` (Advance reserved for `#play-now`) |
| Game Plan | leave-confirm Save | `data-sfx=SFX_COMMIT` + no handler play | one `SFX_COMMIT` (proved with `__gobSfxCalls`) |
| Playbooks | tabs / toggles / normalize / drop | `click-tiny.wav` | `SFX_SELECT` |
| Playbooks | Save button | `confirm-2-lowervol.wav` inside `handleSave` | `SFX_COMMIT` on the button only |
| Playbooks | leave-confirm Save | `data-sfx=SFX_COMMIT` + `handleSave` also played | `handleSave` silent; one `SFX_COMMIT` (proved) |
| Training Report | attribute/stats toggles | `click-tiny.wav` | `SFX_SELECT` |
| Training Report | Back / Office | `click-strong.wav` | `SFX_SELECT` |
| Scouting | Attributes/Stats toggle | none | `SFX_SELECT` |
| Scouting | legacy modal close | `new Audio('/sounds/x-back.mp3')` (bypassed settings) | `playSfx('SFX_SELECT')` |

Muted sfx channel: `__gobSfxCalls === []` on the controls above.

## 4. Tests

- `tests/e2e/prep-scouting-speed-sfx.spec.js` — Game Plan / Playbooks / Training / Training Report / Scouting spies; leave-confirm Save is exactly `['SFX_COMMIT']`, `[]` when muted.
- `tests/e2e/prep-scouting.spec.js` — request order: no `POST /franchise/play-next-game` after clicking Scouting from Training; if team-data and scouting-report both fire they start together. Fixtures now include `next_game_summary`.
- `tests/e2e/retire-prep-embed.spec.js` — same `next_game_summary` so Scouting still resolves without the POST stub.

## 5. Files

- `FrontEnd/static/franchise-command-center.js` — digest/cache opponent; no Scouting POST
- `FrontEnd/static/js/shared/views/scoutingView.js` — parallel scripts + page-life report cache; `performance.mark` on mount/load/paint; toggle SFX
- `FrontEnd/static/js/shared/views/trainingView.js` — no scouting prefetch (A/B <100ms)
- `reports/prep-scouting-speed-sfx/` — measure script, waterfalls, screenshots
- `FrontEnd/static/js/shared/scoutingReport.js` — close through `playSfx`
- `FrontEnd/static/training.js`, `game-plan.js`, `playbooks.js`, `training-report.js` — catalog names
- `tests/e2e/prep-scouting-speed-sfx.spec.js`, `prep-scouting.spec.js`, `retire-prep-embed.spec.js`

Did not touch: `office-home.*`, `officeHome.js`, `gob_nav` / alpha-badge, `check_ui_tokens.py`, `FrontEnd/static/sounds/`.

## 6. Gate counts

Re-run after the 800ms-floor / prefetch follow-up.

- `scripts/ci/check_migration_gates.py`: passed. Gate A 0/0. Gate B 136 lines in 44 files. No `--write-allowlist`.
- pytest `--ignore=tests/e2e -q`: 4180 passed, 14 skipped, 109 xfailed, **1 xpassed** (`test_leaders_view_scope_filters_to_user_conference` — known, list not edited), 0 failed.
- `scripts/check_ui_tokens.py --strict --no-write`: exit 0. Colour-law new 0 / 0 / 0. Legacy 263 / 789 / 0 (1052).
- Full Playwright `--workers=1` port 8159, CI unset, nothing else on that port: **752 passed, 4 skipped**.
