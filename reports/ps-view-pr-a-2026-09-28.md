# Practice Squad view — PR A

Branch `app/ps-tournament-views`. The Practice Squad league (regional pseudo-teams) is Team › Practice Squad (`practice-squad-view`). The user's own practice group stays on Team › Roster. Tournament is unchanged and is not in this commit.

## Backend

No new routes. Both responses are shaped in `BackEnd/practice_squad/browse.py` and returned from the existing cached GETs.

`GET /franchise/practice-squad/standings` returns tiers 1–5 already sorted wins descending, losses ascending, stable. Scrubs (tier 6) stay on the blob and off `tiers`. `win_pct` is `round(wins / played, 3)`, or `0.0` when unplayed, the same rounding as season standings `pct`. The view formats it with `GOBTables.formatPct` and does not recompute it.

`is_user` is the franchise's own regional PS team. The server reads `region` off the user team document (`db.teams`). A row is the user's when `team_id == ps_{REGION}_{tier}` for that tier. A missing or empty region marks every row `is_user: false`, and the view paints no navy row. One navy row per tier card when the region is known.

`GET /franchise/practice-squad/schedule` with no `week` adds `current_week`: the franchise week clamped to 2–19 (week 1 opens on 2; week 20+ opens on 19, history as stored). `week=N` is unchanged and does not include `current_week`.

`GET /franchise/practice-squad/team` still writes the `ps_season_stats` backfill on read. Left as is. The standings and schedule GETs do not write that field. After the offline page load the seeded blob still had `ps_C_1` at 3 wins and no `ps_season_stats_backfilled` key.

## View

`franchise-command-center.html?tab=practice-squad-view`.

- Week 16 and later: the bracket block first, `bracket.js` `renderBracketShared` with `arena: true`, restyled in `gob-views.css` with browse tokens. The connector SVG is taken out of the flex flow so the columns keep their width. Championship line sits above the bracket. Trophy, badge, and logos are hidden.
- Standings: compact tier cards, 3 across at 1280 and 5 at 1920. Navy (`tr.me`) only when `is_user` is true.
- Schedule: one week, week stepper in the subtab tools (same pattern as League › Schedule), URL param `ps_week`. Opens on `current_week`. Two requests (the week list, then that week), not an 18-request fan-out.
- Before init: "Practice Squad has not started yet (available after Week 1 Training Camp)."

Standings team names go to `team-roster-view.html?mode=practice_squad&ps_team_id=…`. That page skips the redirect when both params are present and renders the existing PS roster. Other visits still redirect, then `window.stop()`.

`practice-squad-standings.html` and `practice-squad-bracket.html` redirect to the view and keep the query string. `authGuard` allowlist is unchanged.

Shell: Practice Squad moved from League to Team in `gobShell.js` `SECTIONS` as an in-page view. `TAB_SECTION`, `PAGES`, and `sectionFromReturn` follow it. `#fcc-ps-season-link` points at `tab=practice-squad-view`. Tournament is still `{ id: 'brackets', label: 'Tournament', link: 'brackets', lock: 'tournament' }`. `fallbackHref('practice')` still names `practice-squad-standings.html`, which now redirects into the view.

New CSS in the practice-squad block uses tokens only. The hex already in `gob-views.css` (lines 45, 175, 190, 195) was not touched. Bracket connector strokes stay inside `bracket.js`.

## Screenshots

`reports/ps-view-pr-a/`

| File | What it shows |
| --- | --- |
| `before-init-1280.png`, `before-init-1920.png` | Week 1, not started |
| `week-8-1280.png`, `week-8-1920.png` | In season: 5 tier cards, navy on Region C, Week 8 schedule |
| `week-17-1280.png`, `week-17-1920.png` | Bracket first, championship line, standings still on screen. 1920 also shows the schedule |
| `ps-team-1280.png` | Drill: Casey Lane on the restored PS roster page |
| `offline-week-8-1280.png` | SQLite loopback, stored blob |

Keyboard: the spec focuses the first standings name and checks the focus ring (`outline: 2px solid var(--white)`). The fixture run recorded no page errors and no console errors, including the roster drill.

## Offline

Throwaway file `/tmp/ps-view-offline.sqlite` (not the Application Support save). Seeded the same standings blob as the pytest, then `python -m BackEnd.loopback` on `127.0.0.1:8025`.

`GET /franchise/practice-squad/standings` returned tiers 1–5, order `ps_A_1`, `ps_C_1`, `ps_D_1`, `ps_E_1`, `ps_B_1`, `is_user` on `ps_C_1`, `win_pct` 0.75, no tier 6. Schedule `current_week` was 8. After the page loaded, the blob on disk was unchanged. The loopback was stopped; port 8025 is free.

The offline page logged 404s for `/franchise/team-data` and a few assets. That franchise has no `franchise_team_data` document. The practice-squad view itself rendered from the blob. The fixture spec, which stubs those calls, stayed clean.

## Tests

`tests/test_practice_squad_browse.py`: 8 passed (mongomock and sqlite), 0.54s.

`tests/e2e/practice-squad-view.spec.js`: 2 passed on port 8010 (before init, week 8, week 17, the PS-team drill, both redirects).

`tests/e2e/shell-1b.spec.js`: 5 passed on port 8010. Practice Squad opens `#practice-squad-view`. Tournament still goes to `/brackets.html`.

`tests/e2e/t1-tables.spec.js` was edited (League subtabs no longer list Practice Squad) and was not re-run.

The full suite was not run. Another agent in `~/gob-stats` is running Playwright: `playwright test tests/e2e --workers=1 --reporter=line` with `PORT=8157` (pid 62444, started about 8:59 AM). That run also covers `shell-1`, `shell-1b`, `shell-2`, and `t1-tables`. Schedule the full suite, and a pass of `t1-tables` and `shell-2` in this worktree, after it finishes.

Not touched: cut-players, training-squad-report, box score, sim-rest, the FCC `#schedule-tab` swap, `teamScheduleView.js`, Prep, the sim engine, `cpu_week_pool`, `sim_rng`, finalize.

STATUS: COMPLETE
