# Backlog sweep 1 — 2026-09-27

Branch `fix/backlog-sweep-1`, off `develop`.

## 1. CPU starters

The roster route already marked five starters on every team. On the offline Lancaster copy (`tmp/t1-offline.sqlite`, franchise `6ab284847ab3853ae89a1184`) the route's selector, `projected_starting_five_from_payload`, is the display path of `build_lineup_from_mongo` — the function CPU week sim calls when a team has no lineup yet. There is no other stored CPU lineup. Franchise and franchise-team documents have no lineup field. The only persisted five is `games.opening_lineup`, written after tip from that same selector.

Counts, one pass over all 128 teams: **128 teams, 5 starters each**. None returned `starter=false` for the whole roster.

Little York's five: Frankie Herndon, Derrick Smith, Victor LargeFoot, Wallace Farrabee, Emery Landraneau. That is the same set as Little York's week-2 `opening_lineup`. Derrick is first in `player_ids`, and the next player, Donovan Cotton, is not in the five.

The team page walked that roster order. The Starters divider is one-shot: the first non-starter closes the group, and every later starter is painted under Bench. Derrick was the only starter above the line. The roster view already sorted by `starter` then `lineup_order`. The team page now uses that same order before it draws the compact table.

`tests/test_roster_display.py`: 5 passed on mongomock, 5 passed with `GOB_PERSISTENCE=sqlite` / `GOB_DB_MODE=mongomock`. The route test seats a uuid roster whose payload order is not lineup order and checks the marked ids against the sim selector. The compact team-page spec puts a starter at the end of the payload and expects five player rows between Starters and Bench. That spec passed.

## 2. Standings week snapshot

`GET /franchise/standings` still builds the same rows. A fresh snapshot is a meta document (`gen`, `stale`, `week`, `season`, `built_gen`) plus a body document of those rows. A miss, a stale mark, a week or season mismatch, or a body generation that is not `built_gen` falls back to the live build and stores it. The store is conditional on `gen`. `@browse_cached` is unchanged. Scopes still filter the stored list.

Writers that mark the snapshot stale:

- Phase A (`complete_week_phase_a`) writes the user result into `results.{week}`.
- CPU persist (`persist_cpu_results_only`, used by start-cpu-sims) writes the CPU rows for that week without advancing the week.
- EOS heal (`_eos_heal_phase_from_games`) writes backfilled `results` when it adds rows.
- Team Builder apply writes the display-name overlay the standings rows show.
- Season rollover clears `results` to `{}` and sets week 1 of the next season.

National rank is written by `_apply_regular_season_rank_prestige_updates` before the week-advance transaction. The rebuild in that transaction reads the new ranks, so it is not a separate stale mark. Player-stat finalization does not change standings inputs.

The week-advance rebuild runs inside the existing transaction, next to the leaders rebuild, in both `_finalize_franchise_week_after_cpu_games` and the EOS sim-rest persist. It uses the results and week about to be saved.

`tests/test_standings_snapshot.py` on mongomock and on `GOB_PERSISTENCE=sqlite`: the snapshot equals the live rows (streak, next opponent, pct, differential), and conference, region, user-region, and `region=` filters match. A results write without a stale mark still serves the old rows; after the mark, Beta's streak is `W1`.

SQLite timings on a copy of the Lancaster save, five interleaved pairs, full 128-team payload. Before, back-to-back live builds: 222.6/75.8, 73.0/76.7, 79.6/79.9, 81.6/104.3, 80.0/73.8 ms. Medians 80.0 and 76.7. After, snapshot deleted before each cold call: 238.4/15.2, 86.0/14.5, 79.4/15.3, 87.1/14.7, 87.1/13.7 ms. Medians 87.1 cold and 14.7 warm. Week-advance rebuild: 74.1, 72.6, 88.3, 102.7, 80.1 ms. Median 80.1.

## 3. Flaky tests

### shell-1, "sections and sub-tabs open the matching panel"

The helper clicked a coordinate it had sampled from the rail button. At gob-1280 the rail face is 64px wide and grows on hover, then collapses after a 120ms delay plus the width transition. A point that was on Prep is over the team panel by mouseup, so the section never changes. Alone, the face had already collapsed, so the same click hit Prep.

`locator.click({ position: { x: 16, y: 16 } })` waits until the button is stable and hit-tests the point it clicks. The rail CSS was left alone.

Five runs, workers=1, 10 passed each: 13.1s, 16.4s, 15.4s, 15.6s, 15.7s.

### navigation-fixes-3

Two different clicks were being lost, and one Back was landing on a duplicate locker-room entry.

Mode select awaited the community leaderboard, highlights manifest, and around-the-league fetch before it revealed the page. A stalled one of those left the document on "Checking your session…", including a Back onto a bfcache copy. An aborted auth fetch also sent that copy to login. Those three loads are no longer awaited. An AbortError returns instead of redirecting. A persisted pageshow reveals the page if the loading class is still on. Franchise list, teams, and command center are still awaited before the slots render.

The box-score exit collapses history onto the locker room, then `reloadIfStale` replaces that document so Forward cannot walk back into the game. The replace ran inside the bfcache `pageshow`, and Chrome stored it as a second locker-room entry. Advance was already enabled on the snapshot, so the test's Back ran before the replacement committed and stayed on `franchise-command-center.html?tab=home-tab`. The exit landing now disables `#play-now` and schedules that replace with `setTimeout(0)`, after the traversal commits. A flow-start return (training, lineup) still replaces synchronously.

The training-report "Go To Locker Room" button is in the HTML above `training-report.js`. The tests waited only for `window.GOBNav`, which the head script sets while `document.readyState` is still `loading`. Measured on the failing click: index 2, flow start 1, previous entry the locker room, `readyState` `loading`. The same history with `readyState` `complete` left the report. Chrome drops `history.go` while the document is loading, and a click before the button is wired never calls `exitFlow` at all. The script now wires the button as soon as it runs (`data-exit-wired`). The test clicks that button only after `readyState` is `complete`. `exitFlow` still queues the jump until the load event and the following macrotask when a click does land early, then `history.go`s to the recorded locker-room index.

The standings browser Back had the same ignored traversal. `goBack` during the team-view load did nothing. The page is already `franchise-command-center.html`, so a pathname poll passed while the tab was still `team-view`. That Back now waits for `complete` and polls the tab.

`node --test tests/test_gob_nav.js`: 30 passed, including the deferred exit replace and the load-wait jump.

Five runs of `navigation-fixes-3.spec.js`, workers=1, 9 passed each: 3.6m, 2.9m, 2.1m, 2.2m, 1.9m. Earlier attempts on port 8000 died with `ERR_CONNECTION_REFUSED` because another worktree's `seed_and_serve.py` was already bound there; those runs were discarded. The five greens used port 8001.

### Full suite

`tests/e2e`, workers=1, `desktop-*` ignored: 425 passed, 48 failed, 1 skipped, 14.5m. `navigation-fixes-3` and `shell-1` are not in the failures. The 48 fail on their own and are outside this diff. `fcc-invite-step` evals `updatePlayButton`, which is now a one-line delegate to `GOBAdvance`, so the extracted stub leaves the button on "Run Training". The roster tab has a DEV FOCUS column the column-order spec does not expect. `homepage-v3.html` no longer redirects. The season-advance spec searches source for a call that is no longer in that file.

STATUS: COMPLETE
