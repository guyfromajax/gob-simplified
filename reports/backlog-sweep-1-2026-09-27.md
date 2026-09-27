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
