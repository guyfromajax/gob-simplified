# User-week stats fix — 2026-09-26

Branch `fix/user-week-stats`. A user result is stored only when that game's box score is applied to season stats once. A retry of the same week and the same game still succeeds. The Sim Perf Capstone (sim engine, `cpu_week_pool`, `sim_rng`, and the batched FPD `bulk_write` inside `finalize_game`) was not changed.

## Client root cause

What held the stale id: the desktop session blob `gob:franchise_context` in `localStorage`.

Desktop boots `SessionContextProvider` (`FrontEnd/static/js/shared/franchiseContext.js`). Every hard navigation reloads the page and merges the stored blob with the inbound query (`Object.assign({}, stored, fromUrl)`). Keys the new URL does not mention are kept.

Play Next Game (`gobAdvance.js`) opens set-lineup with `week`, `home`, `away`, and the team ids, and does not send `game_id`. The previous game's `game_id`, `quarter`, and resume flags stayed in the session. Set Lineup treated that id as the current game and skipped `init-game`. Live play, Sim Full Game, and Sim Rest all simulate that id (`bootGame.js` reads `FranchiseContext.get('game_id')`). `finalizeGame.js` then posted phase A with `simData.game_id || simData._id`.

That is why week 2 on the live desktop save rewrote week and team ids onto the week-1 Casino Row document and left its box score in place. `finalize_game` saw the id already in `applied_games` and did not touch season stats. Phase A still wrote `results`.

The web build uses the URL provider, so a link that omits `game_id` does not keep one. Online and desktop share the same phase-A handler. The stale id is a desktop session bug. EOS games use the same `finalizeGame.js` post, so a stale session id would hit them too.

There is a second client gap: phase A received `game_document` only when `simData.final_game_document` was set. A final summary that already contained the box was posted as a score plus the (sometimes stale) id, with no document.

### Client fix

On desktop, if the inbound URL names a different `week`, `home`, `away`, `home_id`, or `away_id` and does not include `game_id`, the session drops `game_id` and the other keys that belong to one game (`quarter`, `period`, `clock`, resume and anchor flags). A refresh of the same matchup still keeps `game_id`. A navigation with an empty query still keeps it (the existing session test).

Set Lineup, when the teams in the URL are a new matchup, clears that page-load id as well, so `init-game` runs. If Play is clicked before that finishes, franchise Q1 now creates a game the same way single-game already did.

`finalizeGame.js` posts the id of the document that owns the box, and sends that document when it has player rows.

## Server guards

In `_complete_week_process_user_game_block`, before any result write, EOS bracket write, or `finalize_game`:

| Case | Response | What is not done |
|---|---|---|
| `game_id` is already in `applied_games`, and the stored game is a different week or a different matchup | 409 `stale_game_id` | No `results` row, no `$set` on that games document |
| A `game_id` or `game_document` was posted, and neither has a box score with players | 409 `missing_box_score` | No `applied_games` / `applied_matchups` claim, no result |
| Same week, same `game_id`, same matchup, already applied | 200, no second GP | `finalize_game` is not called again. If phase A already persisted that week, the route returns `idempotent: true` before this block |
| New id with a box | 200 | Season GP increases by 1 for each player in the box |

`_save_game_result` itself refuses to `$set` week or team ids onto a document whose stored box is a different matchup (409 `stale_game_id`). CPU sims update the document they just created, so they still write.

Requests with no `game_id` and no `game_document` are unchanged. Those are the old score-only harness calls. Every live client path sends `game_id`.

The body is `{"detail": {"reason": "stale_game_id" | "missing_box_score", "message": "..."}}`.

## 409 UX

Phase B is not started when phase A fails, so the week does not advance without a saved result.

If the client is holding a box whose id is different from the rejected id, it posts phase A once more with that id and `game_document`.

Otherwise the end-of-game popup replaces "Go To Locker Room" with the server message and a **Sim this game** button. That button clears `game_id` and the resume keys from the session and opens Set Lineup for the current matchup. `init-game` creates a new document. The user is not left on a dead end, and the old game is not advanced.

## Integrity script

`scripts/check_season_stats_integrity.py` is read-only. It lists teams whose `franchises.results` game count differs from max `season.GP`, and games whose stored team pair disagrees with the box-score teams.

```
GOB_PERSISTENCE=sqlite GOB_SQLITE_PATH=/path/to/save.sqlite \
  python scripts/check_season_stats_integrity.py

python scripts/check_season_stats_integrity.py --sqlite /path/to/save.sqlite
python scripts/check_season_stats_integrity.py --mongo "$MONGO_URI" --franchise-id <id>
```

### Fresh loopback save

`GOB_SQLITE_PATH=/tmp/user-week-stats-fresh.sqlite`, loopback on `127.0.0.1:8765`, new Lancaster franchise `6ab861406fbe98e9d2dba70f`.

- Week 1: Sim Full Game (four `full_sim` quarters), phase A, phase B. Ann Arbor 75–60.
- Week 2: one live quarter (`full_sim` false), then Sim Rest through overtime, phase A, phase B. South Lancaster 57–62.
- Week 3: Sim Full Game, phase A, phase B. Ocean City 71–77.

After each week:

```
SUMMARY gp_mismatches=0 box_disagreements=0 franchises=1
```

### Read-only copies (not repaired)

Live desktop copy `tmp/stats-audit-live.sqlite`, franchise `6ab284847ab3853ae89a1184`:

```
franchise 6ab284847ab3853ae89a1184 week 3 user Lancaster
  GP Lancaster (69a6fcb68d2c56aa82e48a54): results=2 max_season_gp=1
  GP Appalachia (69a6fcb68d2c56aa82e48a5e): results=3 max_season_gp=2
box/matchup game raw:"6ab284bf976adac9fc705b62" franchise 6ab284847ab3853ae89a1184 week 2: box=['Casino Row', 'Lancaster'] stored_teams=['Appalachia', 'Lancaster']
SUMMARY gp_mismatches=2 box_disagreements=1 franchises=1
```

`tmp/offline-parity.sqlite`, same franchise at week 5:

```
franchise 6ab284847ab3853ae89a1184 week 5 user Lancaster
  GP Lancaster (69a6fcb68d2c56aa82e48a54): results=4 max_season_gp=1
  GP Little York (69a6fcb68d2c56aa82e48a58): results=4 max_season_gp=3
  GP Appalachia (69a6fcb68d2c56aa82e48a5e): results=4 max_season_gp=3
  GP IDA (69a6fcb68d2c56aa82e48a60): results=4 max_season_gp=3
box/matchup game raw:"6ab284bf976adac9fc705b62" franchise 6ab284847ab3853ae89a1184 week 2: box=['Casino Row', 'Lancaster'] stored_teams=['Appalachia', 'Lancaster']
SUMMARY gp_mismatches=4 box_disagreements=1 franchises=1
```

## Tests

`tests/test_user_week_stats_gap.py` (mongomock and `GOB_PERSISTENCE=sqlite`):

- Reused id, different week: 409 `stale_game_id`, no week-2 result, week-1 document still Casino Row / Lancaster, GP stays 1.
- No box: 409 `missing_box_score`, no claim, no result, GP stays 0.
- Same week and same game posted twice: second response is `idempotent: true`, one result row, GP stays 1.
- Fresh id with a box: both teams' players go from GP 0 to GP 1, one claim.

Also passed: `test_franchise_context` (new session case: week 2 without `game_id` drops `week-1-game`), `test_franchise_complete_week` (17), `test_office_digest`, `test_leaders_snapshot`, `test_franchise_leaders_endpoint`, `test_persistence_adapter`. SQLite run of the gap tests plus those four modules: 69 passed.

Playwright (`game-start-sequence`, `navigation-fixes-3`, `navigation-history`): 14 passed, 4 failed in `navigation-fixes-3`. The failures are a quarter popup that did not appear within 20s, a Back landing on the training report, and a replayed-quarter case that stayed on the court. The captured logs have no page error from `finalizeGame.js`. They were not re-run.

## Commit

See the git log on `fix/user-week-stats`.

## Pre-merge

`navigation-fixes-3.spec.js`, workers=1, same machine, back to back. Baseline is a clean worktree of `origin/develop` (`276f6931c`), removed with `git worktree remove` after the three runs. Branch is `fix/user-week-stats` (`6e189aa0f`). P = pass, F = fail.

| Test | Baseline 1 | 2 | 3 | Branch 1 | 2 | 3 |
|---|---|---|---|---|---|---|
| training submit lands on the report, then one Back reaches mode-select | P | P | P | P | P | P |
| end-of-game locker room link returns to the locker room, and Forward stays out of the game | P | P | P | P | P | P |
| end-of-game box score exit returns to the locker room | F | F | P | P | P | P |
| standings team page returns instantly with in-app Back and browser Back | P | P | P | P | P | P |
| a corrupted exit index still lands on the locker room | P | P | P | P | P | P |
| custom playbooks adds one step and Back removes it, then training still returns with one Back | P | P | P | P | P | P |
| Enter Franchise gives the locker room its own step, and one Back returns to mode-select | P | P | P | P | P | P |
| a replayed quarter 409 leaves the court unpainted and returns to the lineup | P | P | P | P | P | P |
| recruiting and cut-players exits return to the locker room they started from | P | P | P | P | P | P |

No test failed on the branch in two or more runs. Nothing in `franchiseContext.js`, `set-lineup.js`, `finalizeGame.js`, or `gameCompletionPopup.js` was changed for this check. A new matchup still drops `game_id`. A same-matchup refresh still keeps it.

The four failures from the earlier combined run did not reproduce when this spec ran alone. Three of them (corrupted exit, custom playbooks, replayed quarter) passed all three times on develop and all three times on this branch. The box-score exit failed twice on develop and never on this branch, so it is a pre-existing flake and was left alone. Develop run 1: teardown of that test exceeded the 120s timeout while the locker room was still on "Checking your session" (suite 31.8m). Develop run 2: `backToModeSelect` stayed on the locker room instead of mode-select (suite 1.9m). Develop run 3 passed (1.8m). Branch runs were 1.8m, 1.8m, and 1.7m.

Final sweep on the branch, workers=1, one run: `game-start-sequence`, `navigation-fixes-3`, `navigation-history`, `store-client`, `office-frontend`, `shell-1`, `shell-2`. 62 passed, 1 skipped (`office-frontend` live mid-season digest; the dump file is absent), 3.8m.
