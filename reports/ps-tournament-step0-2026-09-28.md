# Practice Squad + Tournament views — step 0

Branch `app/ps-tournament-views` off `origin/develop` (`46a419443`). Upstream unset. Report only. No code.

Decision already made: Practice Squad moves to the Team section. Tournament stays a League sub-tab and stays locked (`Opens Week N` via `firstTournamentWeek` / `GOBTierEmblem.tierForWeek`) until week 27. Views follow UX §14: `franchise-command-center.html?tab=<view-id>`, registered in `gobViews.js`, old file left as a redirect. News (`news-view`), Awards (`awards-view`), and the two schedule views are the pattern.

Two different “practice squads” exist today. Do not merge them.

- **Your roster’s practice group** is already Team › Roster. `roster-view` concatenates `training_squad` and `practice_squad_recruits` from `GET /roster/{team}`.
- **The Practice Squad league** is the regional pseudo-teams, standings, schedule, and bracket on `practice-squad-standings.html` and `practice-squad-bracket.html`. That is the page that moves to Team › Practice Squad.

## 1. Inventory

| Surface | What it is | Owns | Live? |
|---|---|---|---|
| `practice-squad-standings.html` + `practice-squad-standings.js` | PS league standings and the full schedule. CSS is inline plus `franchise-command-center.css` and `resource-pages.css`. | Those two files | Yes. League › Practice Squad (`gobShell.js` `link: 'practice'` → `#fcc-ps-season-link`, fallback `/practice-squad-standings.html`). |
| `practice-squad-bracket.html` + `practice-squad-bracket.js` + `bracket.js` | Five PS tier brackets and the championship line. | Those files | Yes. Linked from the standings page. Shell `PAGES` marks it browse, League, `keepBack`. |
| `cut-players.html` + `cut-players.js` + `cut-players.css` | Week-1 training-squad assignment, and week-35 real cuts on the same page. | Those files | Yes. Focus page. Advance and the Office todo open it. |
| `training-squad-report.html` + `training-squad-report.js` | “Practice Squad Development” attribute report. Inline CSS. | Those files | Yes. Focus page. News dispatch target. |
| `brackets.html` + `brackets-page.js` + `franchise-tournament-brackets-render.js` + `fcc-tournament-style-a.js` | All franchise tournament brackets (conference, region, national). CSS from `franchise-command-center.css` and `resource-pages.css`. | Those files | Yes. This is the live League › Tournament page. |
| `Tournament Tab.html` | Static mock, “User's Bracket Path”, inline styles, no API. | That file only | No. Nothing in the app links it. Docs mention it as a design. Leave it. |
| FCC `#schedule-tab` `#fcc-tournament-view` | Old in-page swap: week ≥ 27 hides the regular schedule and mounts the same bracket renderer. | `franchise-command-center.html`, `franchise-command-center.js` `applyScheduleTabMode` / `renderTournamentBracket` | Not the live path. The shell maps `?tab=schedule-tab` to `team-schedule-view`. The button `data-tab="schedule-tab"` is gone from the rail. The panel is still in the HTML. |
| `#fcc-ps-season-link` | “Practice Squad Season” anchor inside the old `#recruits-tab`. | `franchise-command-center.html`, href set in `franchise-command-center.js` | The shell reads this href for the League link. The recruits panel itself is not a rail tab (`?tab=recruits-tab` opens Office). |
| Team › Roster practice segment | Your training squad plus practice-squad recruits. | `rosterView.js` | Yes, and it stays. It is not the PS league. |
| Team › Schedule | Weeks 1–26, then three static rows: Conference Tournaments, Region Tournaments, National Tournament. | `teamScheduleView.js` | Yes. Labels only. The bracket stays on League › Tournament (UX §7). |
| League › Schedule | One national week, including EOS weeks 27–34, with `tournament_context` under the team name. | `leagueScheduleView.js` | Yes. Already a module view. |
| Office | Next-game card uses `digest.state === 'tournament'` and `GOBTierEmblem` for weeks 27–34. Todo “Assign practice squad” points at cut-players. “Sim next round” points at `POST /franchise/sim-rest-of-tournament`. | `officeHome.js`, `office_digest.py` | Yes. Office stays a panel. |
| Advance (`#play-now`) | `cut-players`, `sim-rest-tournament`, EOS play CTAs. | `gobAdvance.js` | Yes. Not a browse view. |
| Modals | Bracket reveal, bracket update, region bye. | Built on `GET /franchise/command-center/data`, rendered from the command center | Yes. Overlays, not pages. |
| News | Dispatch “Week N Practice Squad development report” → `training-squad-report.html`. Story type `ps_all_stars` is a stored headline in the feed. | `franchise_routes.py` `_news_dispatch_items`, `_build_ps_all_stars_story` | Yes. Already `news-view`. |
| Tutorial | `tutorial-advanced-practice-squads.html` | Hub link in `gobTutorialHub.js` | Static lesson. Out of this chapter. |
| `team-roster-view.html` + `team-roster-view.js` | JS still loads `GET /franchise/practice-squad/team` when `mode=practice_squad`. The HTML file redirects to `roster-view` or `team-view` before that script runs, and it ignores `mode` and `ps_team_id`. | Redirect in the HTML | The PS-team roster is not reachable. Standings still link here. |
| Box score | `box-score.html?mode=practice_squad` | `box-score.js` | Yes. Flow page. PS schedule and bracket link here. |

Shell section list today (`gobShell.js` `SECTIONS`): Practice Squad and Tournament are both under **League**, not Team. Practice Squad is `link: 'practice'`. Tournament is `link: 'brackets', lock: 'tournament'`. `firstTournamentWeek()` is the first week `tierForWeek` returns a tier, which is 27 (`tierEmblem.js`: 27–29 conference, 30–31 region, 32–34 national; 35+ is null). Before that week the control is disabled, title `Opens Week N`.

`authGuard.js` allowlists `/practice-squad-standings.html`, `/practice-squad-bracket.html`, `/brackets.html`, `/cut-players.html`, and `/training-squad-report.html`.

## 2. Payload

### Practice Squad league

| Route | Cached | Read | Keys the page uses |
|---|---|---|---|
| `GET /franchise/practice-squad/standings` | `@browse_cached` | Live franchise doc `practice_squad` | `initialized`, `week`, `standings` (tier → team id → `{w,l}`), `teams` (`display_name`), `tier_names` |
| `GET /franchise/practice-squad/schedule` | `@browse_cached` | Same blob. Week ≥ 16 also calls `manager._completed_games_for_week` / `_games_for_week` | No `week`: `weeks` only. With `week`: `games[]` (`home_display`, `away_display`, `status`, scores, `game_id`) |
| `GET /franchise/practice-squad/brackets` | `@browse_cached` | `practice_squad.tournaments`, `.championship`, `.teams` | `tournaments[tier].bracket`, `championship` (`game_id`, teams, scores), `teams` |
| `GET /franchise/practice-squad/team` | `@browse_cached` | Franchise blob plus FPD/FRD. **Writes** on read if `ps_season_stats` is not backfilled | `team`, `players`, `projected_starting_five`. Unreachable from the redirect. |

`GOBStore` already prefixes `/franchise/practice-squad`, so those four GETs are store-cached. The standings page does not use `GOBStore`. It `fetch`es standings, then the week list, then one schedule request per week from 2 through 19.

Browser work that UESS puts on the backend:

- Win% is `formatWinPct` in `practice-squad-standings.js`.
- Each tier is sorted by wins, then losses, in that file.
- The schedule page builds the week list and then fans out. Order and “current week open” are client choices. The rows themselves come from the server.

### Cuts and the development report

| Route | Cached | Notes |
|---|---|---|
| `POST /franchise/cut-players` | No | Week-1 assignment. Moves ids onto `training_squad_players`. Requires `cut_required` and an exact count, leaving 12 active. |
| `POST /franchise/cut-players-final` | No | Week-35 hard release. Deletes FPDs. |
| `GET /franchise/training-squad-reports` | **Not** `@browse_cached` | `training_squad_reports` on the franchise, newest week first, plus `attr_keys`. |
| `GET /franchise/command-center/data` | `@browse_cached` | `cut_required` is on this payload. The cut page also loads it and `GET /roster/{team}`. |
| `GET /roster/{team}` | Store prefix `/roster/` | `players`, `training_squad`, `practice_squad_recruits`. |

The development report only formats stored deltas. It does not compute them.

### Franchise tournament

There is no bracket-only browse GET. `brackets.html` loads:

1. `GET /franchise/command-center/data` (`@browse_cached`). During region weeks (30–31) this GET can **write** `region_tournaments` (`reconcile_region_tournaments_with_canonical`) before it responds.
2. `GET /franchise/team-stats` (`@browse_cached`) so the page can build `teamIdToNameMap` and `teamIdMetaMap` (name, mascot, conference, region, `natl_rank`, W, L).

Bracket blobs on the command-center payload, when `eos_tournament_active` or the week-35/36 history flag is set:

- `conference_tournaments`, `region_tournaments`, `national_tournament` — stored on the franchise.
- `eos_tournament` — derived for the current phase (conference weeks slice the user’s conference, region weeks reshape `round1`/`final`, national weeks pass the national blob).
- `user_conference`, `user_region`, `week`.
- Status flags: `user_eliminated`, `offer_sim_rest`, `region_qualified`, `has_eos_game_this_week`, `training_disabled_for_postseason`.
- Modals: `bracket_reveal_modal`, `bracket_update_modal`, `region_bye_modal_eligible`.

`has_bye_this_week` is computed inside `_get_user_eos_phase_status` and is **not** a response key. It is folded into `offer_sim_rest`.

League › Schedule does not read the bracket blobs in the view. `GET /franchise/schedule/week` (`@browse_cached`, weeks 1–34) slices a season bundle. EOS rows come from `_build_eos_schedule_payload`, which projects `conference_tournaments`, `region_tournaments`, `national_tournament`, and `eos_tournament_active` off the franchise and returns `tournament_context`, scores, and `game_id`. That route is the tournament **slate**. The bracket page is the tree.

`POST /franchise/sim-rest-of-tournament` advances brackets. It is an action, not a view read. Do not move it.

SQLite: these reads go through the same franchise document the loopback stores as one row. The schedule builder uses an inclusion projection. Command-center data and the PS routes load the franchise through `verify_franchise_owned_by_user` (full document, including the PS blob and all three tournament blobs). The PS team route and the region-week command-center GET also write. A loopback that is read-only, or a projection that drops `practice_squad` / `conference_tournaments` / `region_tournaments` / `national_tournament`, will not match a full Mongo read. Confirm those keys survive the loopback document before screenshotting offline.

## 3. Phases and states

### Practice Squad league

Constants in `BackEnd/practice_squad/constants.py`.

| Weeks | State | What the user sees |
|---|---|---|
| Before `practice_squad.initialized` | Not started | Standings copy: not started until after Week 1 Training Camp. |
| Week 1, `cut_required` | Roster formation | Advance reads “Assign Practice Squad” and opens `cut-players.html`. Submit writes the training squad and `initialize_practice_squad` runs. This is assignment, not deletion. |
| 2–15 | PS regular season | Tiers 1–5 play. Tier 6 Scrubs exist on the payload (`tier_names`) and are omitted by the page (`TIER_ORDER` is 1–5). |
| 16–18 | PS bracket | `PS_TOURNAMENT_WEEKS`. Brackets route fills `tournaments`. |
| 19 | PS championship | `championship` game on the brackets payload. |
| 20–26 and later | History | Standings and brackets stay on the franchise doc. The page still renders them. No new PS games. |

A save that has finished week 1 can show empty standings. A save around week 8 shows records and played games. Weeks 16–19 need a save that has reached the PS tournament. Scrubs never appear unless a later view asks for tier 6.

### Development report and All-Stars

Weeks 2–26 write `training_squad_reports` and, when someone qualifies, a `ps_all_stars` story on `season_news`. The report page is the dispatch. The All-Stars list is a news story, not a table. Both need a save past week 2. An early-season save with no qualifier has no All-Stars story.

### Franchise tournament

`EOS_CONFERENCE_WEEKS` 27–29, `EOS_REGION_WEEKS` 30–31, `EOS_NATIONAL_WEEKS` 32–34. Initialized at the end of week 26 (`eos_tournament_active`, `conference_tournaments`). National champion clears the active flag. Weeks 35–36 still return the blobs for history (`post_eos_bracket_history_visible`).

| State | How it is decided | Reachable |
|---|---|---|
| Locked | `currentWeek < 27` | Any pre-tournament save. The rail control is disabled. `brackets.html` itself is not locked if you open the URL. |
| Conference, alive | Weeks 27–29 and the user has a game, or is `region_qualified` with no game yet | Play or sim into week 27. |
| Conference bye / waiting | `region_qualified` and no game in weeks 27–29. Advance offers Sim Next Round, not Play | Needs a team that already qualified for the region (conference champ and regular-season title path). Not every save. |
| Eliminated | `user_eliminated` from the phase bracket. Advance offers Sim Next Round until the tournament is over, then next season | Lose a tournament game, or miss the region/national field. Needs that save. |
| Region week-30 bye | `has_bye_this_week` when the user is already in the unplayed region final | The “won the conference tournament and the regular-season title” path. Region bye modal. Needs that save. |
| Region 30–31, national 32–34 | Phase blobs | Sim forward. National only if the team is in that bracket. |
| Finished | `national_tournament.champion`. Office `tournament_complete` at week ≥ 37, or week 35–36 history | Sim to the end. |

Team › Schedule’s three EOS rows are static labels with em dashes. They do not change with results. League › Schedule does: empty copy “No tournament matchups available yet.” when `week >= 27` and the slate is empty.

Screenshot plan: one pre-week-27 save (lock + PS in season or PS history), one week-27 alive save, and extra saves only for the bye, the eliminated team, and the finished national bracket. The calendar itself is one franchise advanced with Sim.

## 4. Proposed mapping

| View id | Sits | Template | Replaces |
|---|---|---|---|
| `practice-squad-view` | Team › Practice Squad. New sub-tab. Remove the League link. | T1. One standings card per tier (same shape as conference standings). Schedule is a second T1 in the same panel, one week at a time, same as League › Schedule. From week 16 the existing PS bracket renderer sits under those tables in the same panel. One `?tab=`. No second URL for the bracket. | `practice-squad-standings.html` and `practice-squad-bracket.html` redirect here (`franchise_id`, `team_id`, return params). |
| `tournament-view` | League › Tournament. Same lock as today (`tierForWeek` / `Opens Week N`). | Not T1/T2/T3. Reuse `fcc-tournament-style-a.js` inside the module panel. The slate stays League › Schedule. | `brackets.html` redirects here. |

Stay focus pages, not module views:

- `cut-players.html` — one-way Advance flow (week-1 assignment and week-35 cuts).
- `training-squad-report.html` — news drill, same role as `training-report.html`.
- `box-score.html?mode=practice_squad` — flow.
- PS pseudo-team roster — do not send it through `roster-view`. `team-roster-view.html` currently drops `mode=practice_squad` and `ps_team_id`. Leave that drill as its own focus page (stop the redirect only when those params are present) until a later view owns `ps_team_id`. Out of PR A’s table work if the redirect is left as a known break; in PR A only if the standings links are repointed.

Leave in place:

- Team › Roster practice segment.
- Team › Schedule’s three EOS label rows.
- League › Schedule’s tournament weeks.
- Office cards, Advance CTAs, reveal / update / bye modals.
- `Tournament Tab.html` (mock).
- Tutorial page.

Inbound links to repoint:

- `gobShell.js` `SECTIONS`: Practice Squad moves from League to Team and becomes an in-page id, not `link: 'practice'`. Tournament stays League, loses `link: 'brackets'`, keeps `lock: 'tournament'`, opens `tournament-view`.
- `PAGES` entries for the three HTML files, once they redirect.
- `#fcc-ps-season-link` and the two href writers in `franchise-command-center.js`.
- `practice-squad-bracket.js` back link (goes away with the redirect).
- `brackets-page.js` is replaced by the view. Its footer already targets `tab=league-schedule-view`.
- `authGuard.js` allowlist stays so the redirect documents load.
- Shell specs (`shell-1`, `shell-1b`, `shell-2`) that expect `/practice-squad-standings.html` and `/brackets.html`.
- UX §7 and §14 section map.

Do not repoint: cut-players, training-squad-report, sim-rest, box score, news story targets, Prep tabs.

## 5. Data gaps

Mark is against a view that only formats. Do not compute these in the browser.

| Need | Mark |
|---|---|
| PS tier standings `{w,l}` and `teams.display_name` | exists on `/franchise/practice-squad/standings` |
| Sorted tier rows | missing (sorted in `practice-squad-standings.js`) |
| Win% | missing (computed in that file). Season standings already return a percent from the server; this route does not |
| `is_user` / navy row on a PS team | missing. No user-team id on the standings payload |
| One schedule week (`games`, displays, scores, `game_id`, `status`) | exists on `/franchise/practice-squad/schedule?week=` |
| All weeks in one body | missing. The no-week response is `weeks` only. A one-week table does not need the missing bundle |
| PS bracket tree and championship | exists on `/franchise/practice-squad/brackets` |
| Scrubs (tier 6) | exists on `tier_names` and standings. The page drops it. Not required for the first view |
| PS team roster | exists on `/franchise/practice-squad/team`. The live redirect never requests it |
| Conference / region / national brackets | exists on `command-center/data` under those names, and as `eos_tournament` for the current phase |
| Team name, W-L, rank, conference, region beside a bracket slot | other route: `/franchise/team-stats` (`team`, `stats.W`, `stats.L`, `natl_rank`, `conference`, `region`). Not on the bracket blob. A single browse body with both is missing |
| Alive / eliminated / has a game this week / region qualified | exists on `command-center/data` as `user_eliminated`, `has_eos_game_this_week`, `region_qualified` |
| Bye this week | missing as its own key. Computed into `offer_sim_rest` |
| Tournament finished | other name: `national_tournament.champion`. Office uses `tournament_complete` inside the digest flags, not as a bracket-view field |
| Round label (Quarterfinal, and so on) | exists in the client as `GOBTierEmblem.roundLabelForWeek`. The schedule payload has `phase` and `round`. A server round name on the bracket view is missing |
| Lock week | exists as code: `tierForWeek` returns conference at 27. No payload field |
| EOS slate for League › Schedule | exists on `/franchise/schedule/week` (`tournament_context`) |
| Development report rows | exists on `/franchise/training-squad-reports` |
| Cut list | exists on `/roster/{team}` plus `cut_required` on command-center data |

UX §14 says a new view moves onto a browse GET the store already caches, and does not add an endpoint. The PS GETs qualify. The tournament page does not: the tree and the team line are two cached GETs, and the join happens in `brackets-page.js`. Putting that join in `tournament-view` would be the derivation this step is not allowed to propose. The gap stays “missing” until a later step adds the display fields to a cached response on the server.

## 6. Risks

- **Sim / finalize.** Bracket writes, week advance, and `sim-rest-of-tournament` live in `franchise_tournament_progression`, `finalize`, and the EOS block of `franchise_routes.py`. Do not edit the sim engine, `cpu_week_pool`, `sim_rng`, or finalize. The views only read.
- **GET that writes.** `command-center/data` reconciles region brackets on weeks 30–31. `/franchise/practice-squad/team` backfills `ps_season_stats`. A view that calls either one will persist. Prefer the PS standings / schedule / brackets GETs, which do not write.
- **Heavy reads.** Command-center data is the whole locker room. The standings page currently fires about 18 schedule requests. A view should use one cached week. Team-stats is a full league table used only as a name dictionary.
- **Offline / SQLite.** Full-document franchise reads include blobs a projection might drop. The region reconcile and the PS backfill need a writable loopback. Screenshot the lock, a PS table, and a bracket on the loopback only after those keys round-trip.
- **Dead FCC schedule swap.** `applyScheduleTabMode` still toggles `#fcc-tournament-view`. The shell never shows `#schedule-tab`. Leave that panel alone or the old and new brackets will both mount.
- **Roster redirect.** Repointing PS team names at `roster-view` shows the user’s practice group, not the pseudo-team.
- **Prep.** Training, game plan, and playbooks are another agent’s. Do not touch those files. The development report is a news focus page, not a Prep tab.

## 7. Suggested PR split

**PR A — Practice Squad.** Move the league page to Team › `practice-squad-view`. T1 standings and a one-week T1 schedule from the existing cached GETs. Bracket block in the same panel from week 16, reusing `bracket.js`. Redirect the two HTML files. Repoint the shell, the FCC href, and the specs. Add sorted rows and win% on the standings response if the table should match the other T1 standings. Leave cut-players, the development report, box score, and the roster practice segment alone. Rough size: one view module, shell and section-map edits, two redirects, a small standings-response addition, e2e for the sub-tab, the lock not applying here, and a week-16 bracket section. Medium.

**PR B — Tournament.** League › `tournament-view`, same lock, Style A renderer, `brackets.html` redirect. Do this after the display-field gap in section 5 is closed on the server. Do not call `sim-rest` or finalize from the view. Rough size: one view module, lock already in the shell, redirect, e2e for locked week 26 and an open week-27 bracket. Medium, and blocked on the payload decision. Larger if that decision becomes a new shape inside `command-center/data`.

PR A does not depend on PR B. PR B does not need the PS view.

STATUS: COMPLETE
