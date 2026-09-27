# Backlog sweep 1 — 2026-09-27

Branch `fix/backlog-sweep-1`, off `develop`.

## 1. CPU starters

The roster route already marked five starters on every team. On the offline Lancaster copy (`tmp/t1-offline.sqlite`, franchise `6ab284847ab3853ae89a1184`) the route's selector, `projected_starting_five_from_payload`, is the display path of `build_lineup_from_mongo` — the function CPU week sim calls when a team has no lineup yet. There is no other stored CPU lineup. Franchise and franchise-team documents have no lineup field. The only persisted five is `games.opening_lineup`, written after tip from that same selector.

Counts, one pass over all 128 teams: **128 teams, 5 starters each**. None returned `starter=false` for the whole roster.

Little York's five: Frankie Herndon, Derrick Smith, Victor LargeFoot, Wallace Farrabee, Emery Landraneau. That is the same set as Little York's week-2 `opening_lineup`. Derrick is first in `player_ids`, and the next player, Donovan Cotton, is not in the five.

The team page walked that roster order. The Starters divider is one-shot: the first non-starter closes the group, and every later starter is painted under Bench. Derrick was the only starter above the line. The roster view already sorted by `starter` then `lineup_order`. The team page now uses that same order before it draws the compact table.

`tests/test_roster_display.py`: 5 passed on mongomock, 5 passed with `GOB_PERSISTENCE=sqlite` / `GOB_DB_MODE=mongomock`. The route test seats a uuid roster whose payload order is not lineup order and checks the marked ids against the sim selector. The compact team-page spec puts a starter at the end of the payload and expects five player rows between Starters and Bench. That spec passed.
