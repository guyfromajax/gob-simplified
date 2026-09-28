# League › Tournament view (PR B)

Branch `app/tournament-view`. League › Tournament is the in-page `tournament-view`, fed only by `GET /franchise/tournament/brackets`.

## Backend (B1)

New read-only route `GET /franchise/tournament/brackets` (`@browse_cached`, week + `browse_rev` stamp). Shaping lives in `BackEnd/tournament/browse.py`. It does **not** call `reconcile_region_tournaments_with_canonical` or any franchise writes.

Returns stored `conference_tournaments`, `region_tournaments`, `national_tournament`, plus `eos_tournament` via the same `shape_eos_tournament()` helper the FCC payload uses (phase picked by calendar week). `teams` is a map of bracket participants only (`name`, `mascot`, `conference`, `region`, `natl_rank`, `W`, `L`, `logo` name key). `round_labels` per phase, `user_team_id`, `user_eliminated`, `eliminated_in_round`, `has_eos_game_this_week`, `has_bye_this_week`, `region_qualified`, `tournament_complete`, `champion`, `first_week` (27), and `locked` when `week < 27`.

**Region staleness:** `region_tournaments_stale` is true when `reconcile_region_tournaments_with_canonical()` would return a new blob (read-only compare). That typically happens in region weeks if the user has not yet hit a code path that reconciles (historically `GET /franchise/command-center/data` or play/complete-week). The browse route serves the stored blob as-is.

`tests/test_tournament_browse.py`: 4 passed (mongomock + sqlite), including no franchise mutation at weeks 30/31.

## View (B2)

`tournamentView.js` registered in `gobViews.js`. Phase segment (Conference · Region · National), default `current_phase`, URL `tournament_phase`. Future phases show “Draws after Week N”. Style A (`fcc-tournament-style-a.js`) with browse tokens in `gob-views.css`; scores use `a.gob-res` when `game_id` is present. User team: `fcc-tb-team--user` (navy edge). Status lines: champion, eliminated round, bye.

Shell: `{ id: 'tournament-view', label: 'Tournament', lock: 'tournament' }` (no `link: 'brackets'`). `brackets.html` redirects to `?tab=tournament-view`. Prep and sim-rest untouched.

## Team › Schedule (B3)

`user_tournament_games_by_phase()` feeds `tournament_by_phase` on `GET /franchise/team-detail`. Week 27+ result rows get `phase` and `round_label` when present in `results`. The 22–26 column lists the user's EOS games under each tournament label with the same `a.gob-res` result link.

## Screenshots (fixtures, port 8010)

`reports/tournament-view/`

| File | State |
| --- | --- |
| `week-26-locked-1280.png`, `week-26-locked-1920.png` | Locked copy, week 26 |
| `week-27-conference-1280.png`, `week-27-conference-1920.png` | Conference bracket, score link, navy user row |
| `week-30-region-1280.png` | Region phase segment |
| `eliminated-1280.png` | “Eliminated in Quarterfinal” |
| `complete-1280.png` | National phase, champion line |

Offline loopback shot was not taken this pass; the route follows the same `@browse_cached` + SQLite path as other browse GETs (`tests/test_tournament_browse.py` sqlite case).

## Tests

`tests/e2e/tournament-view.spec.js`: 3 passed (redirect, locked, conference, region, eliminated, complete).

`tests/e2e/shell-1b.spec.js`: Tournament opens `#tournament-view` in-page (no `brackets.html` navigation).

`tests/e2e/subtabs.spec.js`: week 28 decoration check; FCC subtabs are buttons (0 link tabs).

Full suite: **518 passed, 2 skipped**, ~7.9m, port 8010, `CI` unset, workers=1. Another agent's Playwright was on 8157 during the run; this worktree used 8010 only. Server stopped with the suite.

STATUS: COMPLETE
