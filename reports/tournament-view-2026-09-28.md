# League › Tournament view (PR B)

Branch `app/tournament-view`. League › Tournament is the in-page `tournament-view`, fed only by `GET /franchise/tournament/brackets`.

## Backend (B1)

New read-only route `GET /franchise/tournament/brackets` (`@browse_cached`, week + `browse_rev` stamp). Shaping lives in `BackEnd/tournament/browse.py`. It does **not** call `reconcile_region_tournaments_with_canonical` or any franchise writes.

Returns stored `conference_tournaments`, `region_tournaments`, `national_tournament`, plus `eos_tournament` via the same `shape_eos_tournament()` helper the FCC payload uses (phase picked by calendar week). `teams` is a map of bracket participants only (`name`, `mascot`, `conference`, `region`, `natl_rank`, `W`, `L`, `logo` name key). `round_labels` per phase, `user_team_id`, `user_eliminated`, `eliminated_in_round`, `has_eos_game_this_week`, `has_bye_this_week`, `region_qualified`, `tournament_complete`, `champion`, `first_week` (27), and `locked` when `week < 27`.

**Region staleness:** When `region_tournaments_stale` is true, the browse route still **does not persist**, but the JSON response’s `region_tournaments` is the reconciled blob (same value used for the compare). The flag stays in the payload.

`tests/test_tournament_browse.py`: 5 passed (mongomock + sqlite), including no franchise mutation at weeks 30/31 and `test_stale_region_served_in_response_not_persisted`.

## View (B2)

`tournamentView.js` registered in `gobViews.js`. When `locked` (week &lt; 27): no phase segment — quiet “Tournament opens Week 27” plus phase name / week-range info rows. When live: phase segment (Conference · Region · National), default `current_phase`, URL `tournament_phase`. Future phases show “Draws after Week N”. Style A with `allBrackets: true` so completed national brackets stay visible; browse skeleton only (no `#page-load-overlay` ball spinner). Status block matches Practice Squad championship styling (`.gob-tour-status` eyebrow + display name). User team: `fcc-tb-team--user` (navy edge).

Shell: `{ id: 'tournament-view', label: 'Tournament', lock: 'tournament' }` (no `link: 'brackets'`). `brackets.html` redirects to `?tab=tournament-view`. Prep and sim-rest untouched.

## Team › Schedule (B3)

`user_tournament_games_by_phase()` feeds `tournament_by_phase` on `GET /franchise/team-detail`. Week 27+ result rows get `phase` and `round_label` when present in `results`. The 22–26 column lists the user's EOS games under each tournament label with the same `a.gob-res` result link.

## Screenshots (fixtures, port 8010)

`reports/tournament-view/`

| File | State |
| --- | --- |
| `week-26-locked-1280.png`, `week-26-locked-1920.png` | Locked copy, week 26 |
| `week-27-conference-1280.png`, `week-27-conference-1920.png` | Conference bracket, score link, navy user row |
| `week-30-region-1280.png`, `week-30-region-1920.png` | Region bracket |
| `week-32-national-1280.png`, `week-32-national-1920.png` | National bracket |
| `eliminated-1280.png`, `eliminated-1920.png` | Eliminated status block |
| `complete-1280.png`, `complete-1920.png` | Champion status block + national bracket |
| `offline-week-27-1280.png` | SQLite loopback (`/tmp/tournament-view-offline.sqlite`, port 8025) |

Team › Schedule B3: `reports/team-schedule-columns/team-schedule-w28-tournament-1280.png` (week-28 column, `tr.is-tourney` + `a.gob-res`).

## Tests

`tests/e2e/tournament-view.spec.js`: bracket visible (`.fcc-tb-mu`), no `#page-load-overlay`, redirect, all fixture states above; optional offline test when `TOURNEY_OFFLINE_BASE` is set.

`tests/e2e/shell-1b.spec.js`: Tournament opens `#tournament-view` in-page (no `brackets.html` navigation).

`tests/e2e/subtabs.spec.js`: week 28 decoration check; FCC subtabs are buttons (0 link tabs).

Full suite (fix pass): **517 passed, 3 skipped**, ~7.5m, port 8010, `CI` unset, workers=1. Waited until no other agent Playwright on 8157. Server stopped with the suite.

## Fix pass (2026-09-28)

**Bad screenshots:** E2E did not wait for `#page-load-overlay` to hide (unlike other browse specs), so week-27 shots caught the ball spinner. The complete-state bracket looked empty because Style A week-based reveal hid rounds; the view now passes `allBrackets: true`.

**Modals on tournament tab:** After CC data loads, `championshipMomentsDone.then(…)` in `franchise-command-center.js` normally opens Office/Advance flows. Gated when `?tab=tournament-view` via `fccBrowseTournamentTabActive()` — skips `ConferenceRsRegionModal`, `RegionByeModal`, `WalkOnWelcomeModal`, `RecruitVisitModal`, and `BigNewsModals.maybeShow` (bracket reveal/update, recruiting results). Cut-players and championship-moment queues are unchanged (not in that block).

**Region staleness:** Response serves reconciled `region_tournaments` without writing the franchise doc; `test_stale_region_served_in_response_not_persisted`.

**Offline:** `scripts/seed_tournament_view_offline.py` → throwaway SQLite; loopback on 8025 with `GOB_BUILD_PROFILE=desktop` + `GOB_LOOPBACK_PORT` in the browser (same pattern as desktop e2e).

## Fix pass 2 (2026-09-28)

**Box score link:** Removed the loose `65-72` line under match cards (`fcc-tb-res-link`). Tournament browse passes `boxScoreInTeamRow: true` so each team row’s score is an `a.gob-res.fcc-tb-score` to the same box score — same pattern as Team › Schedule (result column link, not a second line).

**Colour law:** In `#tournament-view`, user matchups use navy edge/tint (`.fcc-tb-mu--user`, `.fcc-tb-team--user` overrides in `gob-views.css`; connector “user” paths use `userConnectorNavy`, no green glow). Green remains only on the shell Advance button. **Gold kept (ch7 reward):** championship matchup card (`.fcc-tb-mu--championship` border/glow), winner crown SVG on championship rows, trophy block badges (`★ CONFERENCE ★` / `★ REGION ★` / `★ NATIONAL ★`), gold winner connector strokes, champion row background (`.fcc-tb-team--champion`).

**Width:** Bracket grids use `width: fit-content` with ~22rem column caps so region (2-round) no longer stretches at 1920; conference and national use the same cap.

**Complete state:** Top `.gob-tour-status` champion block removed when the bracket shows the champion; status block only for eliminated and bye.

**B3:** `reports/team-schedule-columns/team-schedule-w28-tournament-1280.png` (tournament games under phase labels).

**Full suite (fix pass 2):** **517 passed, 3 skipped**, ~7.6m, port 8010, `CI` unset, workers=1, no concurrent Playwright on 8157. Server stopped with the suite.

STATUS: COMPLETE
