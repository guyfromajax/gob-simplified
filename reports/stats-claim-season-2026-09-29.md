# Stats claim season fix: 2026-09-29

Branch `fix/stats-claim-season` @ `d6e586adc` (based on develop `ada9985d7`), pushed to origin. Not merged. **Ready for review.**

## Root cause (confirmed)
| Piece | Finding |
|---|---|
| `franchise_matchup_claim_key` (game_id_utils.py) | Key was `week:teamA:teamB`, with no season |
| `finalize_game` (stat_updater.py) | Skips the whole rollup if the key is in `franchise.applied_matchups` |
| `finish_season` (franchise_routes.py) | Never cleared `applied_matchups` |
| Result | Same pair + same week number in a later season meant box-score stats were silently dropped. W-L unaffected |

**Stop condition checked:** every franchise `finalize_game` caller (complete-week, `save_result`, `sim_rest_of_tournament`, `sim_championship`, `franchise_manager` CPU sim) runs in-season. `finish_season` is gated on week 36. No path finalizes a game after `current_season` has advanced, so reading the season from the franchise doc is safe.

## Diff
| File | Change |
|---|---|
| `BackEnd/utils/game_id_utils.py` | Optional `season` kwarg gives `s{season}:{week}:{a}:{b}`. The legacy format is kept when it's omitted |
| `BackEnd/utils/stat_updater.py` | The claim read also projects `current_season` and passes it to the key |
| `BackEnd/api/franchise_routes.py` | `finish_season` rollover `$set` now has `"applied_matchups": []` |
| `scripts/ws2_{eog_persist_diag,maps_size_compare,mongo_persist_baseline}.py` | Read the franchise season so their un-claim `$pull` matches the new key |
| `tests/test_franchise_finalize_matchup_idempotency.py` | 2 existing tests use season keys; 5 new tests |

**Transition behaviour:** legacy season-less keys in live franchises are ignored straight away, because new keys never match them. So the bug stops on deploy. They are cleared at each franchise's next rollover.

## Tests
New tests:
- The key is season-scoped.
- Same season, week and pair stored as a str `_id` doc and an ObjectId `_id` doc is counted **once**.
- Season 1 week W pair X, then season 2 week W pair X, is counted in **both** seasons.
- A legacy prior-season key doesn't block.
- `finish_season` sets `applied_matchups` to `[]`.

**Red check:** against the unfixed source, 7 of 8 tests in the file fail. That includes the cross-season test, which fails on the dropped stats.

| Run | Result |
|---|---|
| Targeted: idempotency, gp_minutes, user_week_stats_gap, finish_season_resets_results, franchise_game_idempotency, plus the 7 other finish_season test files | **104 passed** |
| Full suite (once) | 4007 passed, 20 skipped, 109 xfailed, 1 xpassed, 43 errors |
| The 43 errors, re-run | **43 passed**. My mistake: I ran the full suite with `-p no:logging`, which removes the `caplog` fixture. They are not related to this change |
| XPASS | `test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`. Listed in known_failures as broken-harness. It's a leaders view and doesn't touch finalize, so probably fixed by the league-polish merge. Someone should remove it from known_failures separately |

**Net: no new failures.**

## `applied_games`
**Not the same bug.** It's keyed on the game `_id`, which is unique per game, so it can't collide across seasons. It is never cleared, so it grows forever, but that's only a size issue. I haven't touched it.

## Staging count
**Skipped.** The worktree has no `.env.local`, so there are no DB credentials. No database was read or written.

## Unsure / notes
- **Test pitfall:** mongomock `update_many` with a whole-dict `$set` (e.g. `{"season": {...}}`) makes the matched docs share one dict object. One player's `$inc` then leaks into another's. The test uses per-field `$set`.
- **Within-season collisions:** not checked. The same pair twice in the *same* week, e.g. two EOS tournaments in one week, would still be deduped. That behaviour predates this change.
- **Base moved:** `origin/develop` advanced to `932b8a2` during the session, so the branch may need a rebase before merge. There are no expected conflicts; that range touched frontend files.
- **Lost stats can't be recovered:** stats already dropped in existing leagues are gone. No backfill was attempted.
