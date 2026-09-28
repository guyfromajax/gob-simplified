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

## Fix pass

### Win %

`GOBTables.formatPct` takes a 0–1 ratio. It runs `Math.abs(n).toFixed(3)` and strips a leading `0`, so `0.875` is `.875`, `1` is `1.000`, and `0.5` is `.500`. Season Standings passes `row.pct` the same way. The view already called `tables.formatPct(row.win_pct)`. The `.500`-only frames were the fixture, which hardcoded `1` or `0.5`. The spec now builds `win_pct` with the server rounding (`Math.round((wins / played) * 1000) / 1000`) and asserts the 7–1 Region B cell is `.875`.

### Bracket tiers

One tier at a time. A white segmented control (`All-Americans · All-Stars · Varsity · JV · Squad`, `.stats-toggle.gob-ps-tiers`, selected chip `var(--white)`) sits above the bracket, default All-Americans. The choice is `ps_tier` in the URL. The user's team stays `mu--user`. A tier with no bracket says "This bracket has not been drawn yet."

### Team links

Standings, schedule, and championship names are `a.gob-team`: plain ink, no underline at rest, underline and `var(--text-100)` on hover and focus. The focus ring is `outline: 2px solid var(--white)`.

### Championship

The raw line is a block above the bracket: eyebrow "Championship", then away · score · home. The score is `a.gob-res` (the box-score link). The higher side gets `is-win` (`var(--text-100)`); the other side is `var(--text-60)`. Before the game is played, both finalists show and the score cell is empty. The block is hidden when there is no championship game, including every week before 19 with an empty championship object. A game that already exists before week 19 is shown.

### Schedule

Away · Result · Home. The completed score is `a.gob-res`. The Box score column is gone. The result column is centered.

### Merge

`origin/develop` is `a67698a5a` ("Merge origin/develop into the practice squad view."). `gobShell.js` auto-merged. The only conflict was `UX_System.md` §7. Both sides kept:

```
| Team | Schedule | `team-schedule-view` ... Four week columns (1–7, 8–14, 15–21, 22–26)... |
| Team | Practice Squad | `practice-squad-view` ... regional practice-squad league. standings and bracket html redirect here. |
| Prep | Training | `training.html`. ... `?tab=training-tab` redirects here. ...
| Prep | Game Plan | `game-plan.html`. ... `resume_from_timeout=true` and `mode=tutorial` stay focus...
| Prep | Playbooks | `playbooks.html`. ...
| Prep | Scouting Report | `coaches-tab` on the franchise command center. ...
```

`gobShell.js` `PAGES` after the merge:

```
'/practice-squad-standings.html': { kind: 'browse', section: 'team', sub: 'practice-squad-view' },
'/practice-squad-bracket.html': { kind: 'browse', section: 'team', sub: 'practice-squad-view', keepBack: true },
'/training.html': { kind: 'browse', section: 'prep', sub: 'training-tab' },
'/training-report.html': { kind: 'browse', section: 'prep', sub: 'training-tab' },
'/game-plan.html': { kind: 'browse', section: 'prep', sub: 'game-plan-tab' },
'/playbooks.html': { kind: 'browse', section: 'prep', sub: 'playbooks-tab' },
```

Team › Practice Squad stays in `SECTIONS`. Prep's `PREP_EDITOR` map is untouched. `window.stop()` after the roster redirect was removed; it cancelled `location.replace` and hung `page.goto`.

### Tests

`ps` showed no other Playwright. Port 8010, `CI` unset, workers=1.

`practice-squad-view.spec.js`: 2 passed, including `.875`, `ps_tier=2`, the championship score link, and the unplayed-finalists case.

`t1-tables`, `shell-1`, `shell-1b`, and `shell-2` passed in the targeted run and again in the suite. `shell-1` now falls back to the locked Tournament control when League has no `<a class="tb">` at week 1.

The first full suite was 3 failed, 514 passed. The failures were source checks that still expected `team-roster-view.html` to be a stub, and `subtabs.spec.js` counting unselected link tabs at week 3 (zero, because Practice Squad is in-page and Tournament is locked). Those specs now accept the practice-squad roster page and open the underline check at week 28, when Tournament is an `<a>`. The three re-passed.

Full suite after that: 515 passed, 2 skipped, 0 failed, 7.5m. The server exited with the suite. Port 8010 is free. Regenerated tracked report images were restored. The retaken frames stay in `reports/ps-view-pr-a/`: `week-8-1280.png`, `week-8-1920.png`, `week-17-1280.png`, `week-17-1920.png`, `record-1280.png` (7–1 reads `.875`).

STATUS: COMPLETE
