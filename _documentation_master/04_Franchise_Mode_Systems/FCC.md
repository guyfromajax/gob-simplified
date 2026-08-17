# Franchise Command Center (FCC)

The Franchise Command Center is the franchise-mode hub. It is the user’s primary season-management surface and the launch point for training, next-game flow, recruiting, scouting, playbooks, EOS tournament handling, and season rollover.

This document is intended to be the full FCC reference for future work in new threads. It covers:

- current live user-facing behavior
- actual frontend structure and tab set
- data wiring and cache behavior
- known legacy / unreferenced code still present in the implementation
- current API load shape and optimization targets

Source of truth:

- [franchise-command-center.html](/Users/jamesdavies/gob-simplified/FrontEnd/static/franchise-command-center.html)
- [franchise-command-center.js](/Users/jamesdavies/gob-simplified/FrontEnd/static/franchise-command-center.js)
- [franchise-command-center.css](/Users/jamesdavies/gob-simplified/FrontEnd/static/franchise-command-center.css)
- [franchise_routes.py](/Users/jamesdavies/gob-simplified/BackEnd/api/franchise_routes.py)

---

## Purpose

FCC is not just a “menu page.” It is a stateful command center with:

- persistent franchise identity
- week / season awareness
- CTA switching based on franchise lifecycle state
- local tab navigation
- cached summary data for fast return
- links into deeper routed franchise pages

The page is designed to feel like one persistent headquarters location even when some workflows route to separate pages.

---

## Required Context

### URL

FCC requires:

- `franchise_id`

Optional but commonly present:

- `team_id`
- `tab`
- `return_url`

Important rule:

- `franchise_id` must come from the URL
- if `franchise_id` is missing, FCC redirects to `franchise-select-team.html`

### Team identity

FCC resolves the user team from:

1. `team_id` URL param if present
2. `localStorage.franchise_user_team_id`
3. `/franchise/command-center/data` response if not already resolved

The frontend stores:

- `userTeamId`
- `userTeamNameForLeaders`
- `userConference`
- `userRegion`

---

## Top Shell

The FCC shell includes:

- left: `Exit Franchise`
- center:
  - team banner logo
  - `Season X / Week Y`
  - `Record: W-L`
  - `National Rank: #`
- right:
  - primary hero CTA `#play-now`

The shell colors can shift based on account display-color preference:

- default FCC palette
- team-color mode using the user team’s primary color

This is hydrated via:

- `/api/auth/me`
- `commandCenterTopDataCache.primary_color`

---

## Primary CTA State Machine

The top-right hero button is not static. Its label and behavior are controlled by `updatePlayButton(topData)`.

Possible regular-season and fallback labels:

- `Run Training`
- `Run Training Camp`
- `Play Next Game`
- `Cut Players`
- `Recruiting`
- `Go To Next Season`
- `Sim Next Round`

Postseason weeks 27-34 replace the generic play/sim labels with the tournament-round labels documented below.

### Current mode mapping

- `training`
  - before weekly training is completed
  - routes to `training.html`
- `play`
  - after training is complete and user can play next game
  - calls `/franchise/play-next-game` then routes to `set-lineup.html`
- `cut-players`
  - week-1 post-training-camp cuts required
  - routes to `cut-players.html`
- `week35-recruiting`
  - week 35 recruiting orders state
  - routes to `recruiting-orders.html`
- `sim-rest-tournament`
  - EOS case where user is eliminated or has a bye and can advance bracket state
  - calls `/franchise/sim-rest-of-tournament`
- `new-season`
  - week 36 or tournament-complete rollover state
  - shows confirmation modal
  - calls `/franchise/finish-season`

The primary CTA plays `confirm-1-lowervol.wav` on click. For CTA branches that navigate away or reload the FCC, the controller waits for a 200 ms confirm-SFX guard before changing pages so the quieter WAV is audible.

### EOS-specific behavior

The CTA logic depends on:

- `eos_tournament_active`
- `eos_tournament.completed`
- `training_disabled_for_eos`
- `training_disabled_for_postseason`
- `user_eliminated`
- `offer_sim_rest`
- `cut_required`
- `week`

During franchise postseason weeks 27-34, `training_disabled_for_postseason` skips the normal Run Training CTA. Existing eliminated, bye, week 35 recruiting, and season rollover states keep priority.

Postseason CTA labels preserve the existing `play` and `sim-rest-tournament` behaviors:

| Week | Active user CTA | Eliminated/bye user CTA |
|------|-----------------|--------------------------|
| 27 | `Play Conference Tourney First Round` | N/A |
| 28 | `Play Conference Tourney Semifinals` | `Sim Conference Tourney Semifinals` |
| 29 | `Play Conference Tourney Championship` | `Sim Conference Tourney Championship` |
| 30 | `Play Region Tourney First Round` | `Sim Region Tourney First Round` |
| 31 | `Play Region Tourney Championship` | `Sim Region Tourney Championship` |
| 32 | `Play National Tourney First Round` | `Sim National Tourney First Round` |
| 33 | `Play National Tourney Semifinals` | `Sim National Tourney Semifinals` |
| 34 | `Play National Championship!` | `Sim National Championship` |

A user with a Region Tournament bye is active but uses the week 30 sim-rest state, so the CTA is `Sim Region Tourney First Round`.

---

## Live FCC Tabs

The current live tab bar contains:

1. `Coach's Office`
2. `Roster`
3. `Player Stats`
4. `Team Measures`
5. `Game Plan`
6. `Playbooks`
7. `Scouting Report`
8. `Standings`
9. `Schedule`
10. `Team Stats`
11. `Leaders`
12. `News` (tab id is still `press-tab`)
13. `Recruits`
14. `Inbox`

Important clarification:

- FCC currently has **no live Resources tab**
- instead, several tabs include footer links out to standalone routed pages like standings, schedule, team stats, leaders, rankings, and recruiting

---

## Coach’s Office

`Coach’s Office` is the default FCC tab.

It renders an eight-card summary grid:

1. `Standings`
2. `Next Game`
3. `Locker Room`
4. `Recruiting`
5. `National Rankings`
6. `Last Game`
7. `Player Scoring`
8. `News`

### Card behaviors

#### Standings

- shows only the user conference teams
- rendered from `standingsDataCache`
- columns:
  - Team
  - W
  - L
  - PF
  - PA

#### Next Game

- built from `topData.next_game_summary`
- shows:
  - matchup label (`vs` / `@`)
  - opponent banner
  - opponent team name + mascot + region/conference (`opponent_team_name` + `opponent_team_mascot` + `opponent_team_region/opponent_team_conference`, e.g. `Providence Freeze (B3)`)
  - opponent record and rank on one meta row (`Record: W-L`, `Rank: #`)
  - top scorer
  - top rebounder

#### Locker Room

- built from `teamData.team_attributes` and `userRosterPlayersCache`
- shows:
  - Team Chemistry bar
  - Player Attitudes emoji distribution

#### Recruiting

- shows lean recruits summary table
- columns:
  - Recruit
  - Arch.
  - HT
  - WT
  - RT

#### National Rankings

- top 10 national rankings slice from `topData.rankings`
- includes footer link to full rankings page

#### Last Game

- built from `topData.last_game_summary`
- POTG is calculated from the finalized persisted game document using the canonical EOG-modal rules: identical scoring, `REB` fallback, merged candidate sources, 16-point separation rule, and game-id-seeded 67/33 contender selection. Cross-language parity is enforced by `tests/test_potg_surface_parity.py`.
- shows:
  - matchup label
  - opponent banner
  - final score
  - Player of the Game
  - POTG stat line

#### Player Scoring

- top 12 user-roster players sorted by PPG, then RT
- displays player name and PPG only

#### News

- live: renders up to 5 most recent headlines from `topData.news_headlines`
- each headline links to the standalone news page (`news.html?story_id=...`)
- `See All News` link sits in the card header row, right-justified
- empty state: `No News To Report`
- see `06_GMO_Supporting_Systems/News_System.md` for story generation

---

## Roster Tab

The `Roster` tab renders the user roster table.

Columns:

- Name
- POS
- Year
- Height
- Weight
- SC
- SH
- ID
- OD
- PS
- BH
- RB
- AG
- ST
- ND
- IQ
- FT
- RT

Data source:

- `RosterLoader.loadRosterWithStats(...)`
- roster endpoint:
  - `/roster/{team_id}?franchise_id=...&profile=1`
- franchise state endpoint:
  - `/franchise/state?franchise_id=...&profile=1`

Notes:

- roster data is cached in `userRosterPlayersCache`
- header tooltips are initialized through `attributeTooltips.js`

---

## Player Stats Tab

The `Player Stats` tab shows the user roster’s season player stats table.

Columns include:

- Player
- PTS
- FGM
- FGA
- FG%
- 3PTM
- 3PTA
- 3PT%
- FTM
- FTA
- FT%
- DREB
- OREB
- TREB
- AST
- STL
- BLK
- F
- MIN
- TO
- SCRA
- SCR%
- DEFA
- DEF%

Rendering uses the roster/player stats pipeline rather than a separate FCC-only endpoint.

---

## Team Measures Tab

The `Team Measures` tab is the current user-team attribute summary.

It shows:

- radar chart
- Shooting linear card
- Rebounding linear card
- Team Chemistry card

Data source:

- `teamData.team_attributes`
- loaded from `/franchise/team-data`

Important implementation note:

- FCC also performs an early `/franchise/team-data` fetch specifically to override `topData.team_chemistry` for the top-bar chemistry display so the top shell and Team Measures tab stay aligned

---

## Game Plan Tab

The `Game Plan` tab renders the current strategic settings summary.

It displays human-readable interpretations of strategy sliders in the same two-column order as `game-plan.html` (left column, then right column, row by row):

**Left column**

- Offense
- Inside
- Attack
- Outside
- Offense Tempo
- Play Alteration

**Right column**

- Defense
- Aggression
- Half-Court Trap
- Full-Court Press
- Fast Breaks
- Rebounding

Examples:

- `100% Motion`
- `50% Motion / 50% Set Plays`
- `100% Zone`
- `Aggressive`

CTA:

- `Edit Game Plan`
- routes to `game-plan.html` with franchise context and `return_url`

Data source:

- `/api/gameplan?mode=franchise&franchise_id=...&team_id=...`

---

## Playbooks Tab

The `Playbooks` tab renders the current playbook summary plus Playcall Center.

Sections:

1. Motion Plays
2. Set Plays
3. Man Defense
4. Zone Defense
5. Fast Breaks
6. Press/Trap
7. Playcall Center

### Motion / Set Plays / Defensive sections

Each item card shows:

- play name
- percentage
- effectiveness
- optional top scorer

Set Plays also display the target shooter in parentheses, for example:

- `Double Screen Three - Wing (SG)`

### Press/Trap

- currently placeholder
- displays `In Development`

### Playcall Center

Playcall Center shows two 8-slot ordered columns:

- Offense
- Defense

Each slot shows:

- slot number
- assigned play / defense
- optional detail

CTA:

- `Edit Playbooks`
- `Edit in Playbooks`
- both route to `playbooks.html` with franchise context and `return_url`

Playbook freshness:

- FCC checks whether playbooks were saved for the current week
- stale playbooks trigger a visual warning state on the legacy playbooks button hook

Data source:

- `/api/playbooks?mode=franchise&franchise_id=...&team_id=...`

**Effectiveness wiring (Playbooks tab):** Motion and set rows take **`effectiveness` from each entry in `team_obj["plays"]`** (same object the API lists). Man and zone defense rows are **synthetic rows** keyed by playbook ids (`man_normal`, `zone_23`, …); their **`effectiveness` is read from `scouting_data["defense"]`** using the **canonical defense row key** (`man`, `2-3-zone`, …), with **legacy scouting keys** (`Man`, `2-3 Zone`, …) still accepted during migration (`read_scouting_defense_row` in `BackEnd/utils/defense_identity.py`, used when building `GET /api/playbooks`).

**When CMD moves:** Install training increases motion/set **and** canonical defense effectiveness. **Defense** still gets a small **random** pre-training decay at the **start** of each training session (skipped training camp). **Offense** play CMD is **not** decayed in training; after each **franchise** game, EOG reduces each offensive play’s effectiveness on FTD by **`int(percent_share_of team times_run)`** from that game’s playcall mix (`End_Of_Game_System.md`, `build_eog_offensive_play_effectiveness_decay_ftd_updates` in `training_execution_v2.py`).

---

## Scouting Report Tab

The `Scouting Report` tab replaces the old modal-style scouting flow with an embedded tab view.

It renders:

1. upcoming opponent summary
2. projected starting five (**image cards**, not the old attribute table)
3. opponent Team Measures
4. opponent Play Usage (Last Game)

### Opponent resolution

FCC resolves the upcoming opponent by:

1. reading top data / EOS state
2. calling `/franchise/play-next-game`
3. comparing the returned matchup to the user team

Scouting remains available in **regular season and EOS tournament weeks 27–34** (while the user team is still alive). The same FCC tab + `/franchise/scouting-report` path is used; there is no separate tournament scouting surface for franchise EOS.

**Restored-tab lifecycle:** Returning from another screen with `?tab=coaches-tab` activates the tab immediately, but its renderer awaits the single FCC initialization promise before resolving the matchup. This guarantees that `commandCenterTopDataCache`, the authoritative user team id, and user-team name are available. A normal post-load tab click observes the already-settled promise. Do not replace this contract with timing delays or duplicate post-init fetches.

**Film Study gating:**

- Regular-season weeks: opponent Play Usage is gated by the user's current-week **Film Study** training allocation. HCO play usage unlocks at Film Study `> 0`; Fast Break and Half-Court Trap usage unlock at Film Study `> 1`.
- EOS tournament weeks **27–34**: training does not run, so the Scouting Report bypasses Film Study gating and shows all available Play Usage panels.

### Opponent data fetches

When the tab opens, FCC loads:

- `/franchise/team-data?franchise_id=...&team_name={opponent}`
- `/franchise/scouting-report?franchise_id=...&team_name={opponent}`

The opponent summary also uses:

- standings cache first
- rankings cache as the W/L fallback

Current summary fields:

- opponent name
- opponent record
- opponent national rank

### Projected Starting Five (image cards)

Visual source: `projects/Scouting - Projected Five (Images).html`.

- Lazy-rendered on tab open via `renderScoutingTab()` → `renderFccScoutingProjectedLineup()` → `renderProjectedStartingFiveCards()` in `js/shared/scoutingReport.js`. Does **not** touch FCC initial load / page-load overlay.
- **Selection is the five autoset would field at tip** — same eligibility waterfall, exact max-weight DP and energy-aware objective as the game, via `db_utils.projected_starting_five_from_payload()`. See `06_Gameplay_Systems/CPU_Team_Rotation_System.md` §6. Opponents are CPU teams and never override their lineup, so this tab is an **exact** match for what walks onto the floor. Was a separate greedy fill until August 2026.
- Cards ordered PG → SG → SF → PF → C.
- Each card: square headshot (`API_CONFIG.getPlayerImageUrl(player_id, { size: 'card' })`, `loading="lazy"`, explicit 240×240, `onerror` → generic headshot), white position badge, RT badge colored with `getRtBucketClass` / `rt-buckets.css`, name + `#jersey`, year · height · weight, boxed PPG / RPG / APG / DEF%.
- Per-game stats and DEF% are **server-enriched** on each `projected_starting_five` row (`ppg`, `rpg`, `apg`, `def_pct`) via shared `build_enriched_projected_starting_five()` (`scouting_utils.py`) using FPD `season` totals (`PTS`, `TREB`/`OREB`+`DREB`, `AST`, `GP`, `DEF_S`/`DEF_A`). DEF% is a whole percent (`round(DEF_S/DEF_A*100)` when `DEF_A > 0`, else `0`).
- The same card renderer and enrichment helper power **team roster Starting 5** (`team-roster-view.html`) from `GET /roster/...` / Practice Squad team payloads (header label **Starting 5**; FCC keeps **Projected Starting Five**).
- Core attribute columns are **not** shown in this section anymore (team attributes remain under Team Measures / team page).
- ⚠️ **The attribute values on `projected_starting_five` rows are ALREADY on the 0–10 display scale** — `compute_projected_starting_five()` applies `int(raw) // 10` server-side (pinned by `test_attributes_floor_ten_in_output`). The table renderer (`renderProjectedStartingFive`, used by the Training Report and tournament scouting) must print them as-is. It divided by 10 a second time until 2026-08, flooring every attribute to `0` — only a perfect 100 survived, as `1` — which read as training deltas rather than totals.

Important note:

- legacy `#scouting-report-btn` modal behavior is explicitly removed by `disableLegacyFccScoutingModal()`
- The scouting opponent record must not rely only on `standingsDataCache`: FCC loads standings with `scope=user_region`, so national championship opponents can be outside that scoped payload. `commandCenterTopDataCache.rankings` is national and includes `W` / `L`, so it is the required fallback for opponent record display.

---

## Standings Tab

The FCC standings tab is still the slim FCC-specific standings view, not the full national standalone page.

Current behavior:

- renders the user conference plus sister conference when available
- each conference gets its own card
- team names link to roster view
- footer link routes to full standings page

Columns:

- Team
- W
- L
- PF
- PA
- Next

Primary data source:

- `/franchise/standings?franchise_id=...&scope=user_region&team_id=...&profile=1`

Fallback behavior:

- if the payload doesn’t include FCC-specific conference slices, the renderer can still display a full region grouping view
- that fallback is more relevant to shared standings rendering than normal FCC flow

---

## Schedule Tab

The `Schedule` tab is live again inside FCC.

Layout:

- four schedule columns
- grouped as:
  - Weeks 1–7
  - Weeks 8–14
  - Weeks 15–21
  - Weeks 22–26 plus tournament markers

Display logic:

- incomplete games show matchup only
- complete games show matchup plus user-team score result
- completed rows receive win/loss/tie styling

Tournament rows appended at end of last column:

- Conference Tournaments
- Region Tournaments
- National Tournament

Data source:

- `/franchise/schedule?franchise_id=...&user_team_only=1`

Cache:

- `userScheduleDataCache`

Footer link:

- routes to full `schedule.html`

---

## Team Stats Tab

The `Team Stats` tab is the FCC team-stats summary table across all teams.

It is not the same as the `Team Measures` tab.

Columns include:

- Team
- Rank
- W
- L
- PF
- PA
- FGM / FGA / FG%
- 3PTM / 3PTA / 3PT%
- FTM / FTA / FT%
- DREB / OREB / TREB
- AST / F / TO / SCRA / SCR%
- STL / BLK / DEFA / DEF%

Formatting:

- DEF% is displayed as a whole-number percent everywhere in FCC (`round(DEF_S/DEF_A*100)`), including leaders, player stats, team stats, POTG summaries, and projected-starting-five cards.

Data source:

- `/franchise/team-stats?franchise_id=...&scope=conference`

Cache:

- `fccTeamStatsSummaryCache`

Footer link:

- routes to standalone `team-stats.html`

---

## Leaders Tab

The `Leaders` tab shows FCC summary leader cards, not the full leaders page.

Current request:

- `/franchise/leaders?franchise_id=...&scope=season&view_scope=conference&limit=5`

Cache:

- `leadersDataCache`, keyed by server scope and limit. Conference remains the summary default. Any conference/region/national scope control requests that exact `view_scope`; it does not attempt to reconstruct a broader leaderboard by filtering an already conference-limited response.

Footer link:

- routes to standalone `leaders.html`

---

## News Tab

The tab labeled `News` (tab id `press-tab`) is live and always visible regardless of week.

Behavior:

- lazy-fetches `GET /franchise/news?franchise_id=...` on first open (cached in `fccNewsListCache`)
- renders all season stories grouped by release week, newest week first
- each story links to the standalone `news.html` page
- empty state: `No News To Report`

---

## Recruits Tab

The `Recruits` tab has two live modes depending on week.

### Weeks 1–35

Shows recruits leaning toward the user team.

Source:

- `topData.lean_recruits`
- `topData.team_name_map`

Default sort:

- RT descending

Columns:

- Name
- Home Region
- Archetype
- HT
- WT
- POS
- YR (recruit year: JH / FR / SO / JR)
- SC
- SH
- ID
- OD
- PS
- BH
- RB
- AG
- ST
- ND
- IQ
- FT
- RT
- Current Lean

### Week 36+

Shows signed recruits and walk-ons.

Source:

- `topData.week_35_user_recruits`

Differences:

- heading changes to `Signed Recruits`
- `Current Lean` column is hidden
- walk-ons append `(walk on)` to the name

Footer link:

- routes to standalone `recruiting.html`

---

## Inbox Tab

The `Inbox` tab is now a live hybrid of:

1. persisted season inbox items
2. synthetic training-report shortcut

### Persisted season inbox

Source:

- `topData.season_inbox`

Current supported live type:

- `game_result`

Format:

- `Week #7: Morristown defeated Lancaster 68-61 box score`
- `Week #8: Morristown lost to Little York 59-64 box score`

Behavior:

- newest items appear first
- items persist for the full season
- reset when next season initializes

### Training report link

Source:

- `topData.last_training_report_week`

Format:

- `Week 3 training report here.`

Link target:

- `training-report.html?...&from=inbox`

Important system note:

- the training item is still synthesized from franchise state
- the game-result items are persisted in `season_inbox`
- FCC renders the synthesized training-report item at the top of the Inbox
- persisted `season_inbox` game-result items render underneath it in newest-first order

If neither source produces items:

- FCC renders `Inbox is empty.`

---

## Recruiting Surface Outside The Recruits Tab

FCC also has a separate recruiting status/button state in the hero area, driven by `updateRecruitingButton(topData)`.

Current logic:

- weeks 1–18:
  - no button
  - live copy: `Recruiting Invites Begin Week 20`
- week 19:
  - no button
  - live copy: `Recruiting Invites Begin Next Week`
- weeks 20–26 before current-week results:
  - no button
  - live copy: `Recruiting Invites Active`
- weeks 20–26 after results for current week:
  - button visible
  - copy: `Week X Recruiting Visits`
  - routes to `recruiting-results.html`
- week 35:
  - live copy: `Recruiting Is Live`
- week 36:
  - live copy: `Recruiting Is Complete`
- post-26 otherwise:
  - live copy: `Recruiting Runs After National Tourney`

Implementation note:

- `updateRecruitingButton(...)` now drives **two live footnote surfaces** via paired element ids: `fcc-recruiting-live-copy-home` / `fcc-recruiting-btn-home` (Coach's Office) and `fcc-recruiting-live-copy-tab` / `fcc-recruiting-btn-tab` (Recruits tab footer)
- the old single hero ids (`#fcc-recruiting-btn` / `#fcc-recruiting-live-copy`) are gone

---

## EOS Tournament Surface

FCC still handles the EOS tournament directly.

### Trigger window

- conference tournament: weeks 27–29
- region tournament: weeks 30–31
- national tournament: weeks 32–34
- bracket history remains visible through weeks 35–36

### Current bracket presentation

The renderer stacks tournament history sections:

- Conference Tournament
- Region Tournament
- National Tournament

depending on current week / phase.

Visual tones:

- conference tone
- region tone
- national tone

Renderer:

- shared `renderBracketShared()` from [bracket.js](/Users/jamesdavies/gob-simplified/FrontEnd/static/bracket.js)

Supporting data:

- `topData.eos_tournament_active`
- `topData.eos_tournament`
- `topData.conference_tournaments`
- `topData.region_tournaments`
- `topData.national_tournament`

Extra team-name mapping fetch:

- `/franchise/team-stats?franchise_id=...`

### EOS side effects reflected in FCC

- training may be disabled for eliminated teams
- hero CTA becomes the week-specific tournament simulation label
- champion completion is announced via Championship Announce Moments (`pending_championship_moments`); see [Championship_Announce_Moments.md](Championship_Announce_Moments.md)

---

## Championship / Season-End Modals

FCC currently owns several modal flows:

### Championship Announce Moments

Queued championship overlays from `topData.pending_championship_moments`, rendered by `window.ChampionshipMoments` on FCC mount. See [Championship_Announce_Moments.md](Championship_Announce_Moments.md).

### Cut Players Required

Shown when:

- `topData.cut_required`
- `topData.cut_count > 0`

### Go To Next Season

Confirmation modal shown before calling:

- `/franchise/finish-season`

### Recruiting Presence (three levels)

Recruiting is a first-class FCC presence all season. Levels are driven by **state, not phase**.

| Level | Fires when | Element |
|---|---|---|
| Ambient | Nothing needs the player | Coach's Office Recruiting card (the Wire) |
| Prompted | Board unsent this week, or unseen wire events | Secondary hero button + `.inbox-badge` on the Recruiting tab |
| Gated | Week 20 with no board · Week 35 | `#play-now` itself |

**Colour law.** Green is reserved for the gating action. The secondary button is always amber (`#F79420`) because it is always skippable; recruiting only turns green when it *becomes* `#play-now`.

**Secondary button** lives in the previously-empty second slot of `.hero-buttons-group`. Its state comes from `recruitingButtonState()` (`js/shared/recruitingButtonState.js`) — a pure function, so all five states are unit-tested without a DOM. It has its own `.fcc-rec-btn` class rather than a `.hero-btn` modifier: the green gradient lives on `.hero-btn` itself, so a modifier would have to fight inheritance and any miss would paint a non-gating control green. Both buttons are `width: 186px` so they share a right edge.

**Week-20 gate** sits in `updatePlayButton` immediately after `cut_required` — an illegal roster outranks an empty board. Mode `build-invite-board`.

**Out of Run Training.** `training.js` no longer routes to recruiting. Only the **route** was removed: the invite still fires on week advance using whatever board exists, so no week can be silently lost. Decoupling the *execution* was built and reversed once because Run Training was the only guaranteed weekly trigger — do not re-decouple it.

**Read marker.** `recruiting_wire_seen_week` stores a **week number, not a boolean** — a season-scoped boolean cannot distinguish "seen week 12's events" from "seen week 13's". Stamped by `PATCH /franchise/recruiting-wire-seen` when the player **opens** the Recruiting surface; never on hover (reading the tooltip must not clear the badge) and never on FCC render.

**Board-sent marker.** `recruiting_board_saved_week` records the week the visit-window board was last saved. FTD `Recruits` persists across weeks and so cannot answer "sent *this* week", which the button's `.is-dead` state needs.

**The Wire card** spans two columns and renders `recruiting_lean_events` (Prompt 1) — gains *and* drops, newest first, with a phase-appropriate status line. `.fcc-drop-badge` / `.fcc-drop-row` mirror the existing `.fcc-newlean-*` geometry exactly, differing only in accent token, so drops can never render quieter than gains. Standings was retired to keep the grid at rows of 4; see `Season_Init_System.md` cross-reference below and §5.5 of the build plan.

Grid: `Locker Room │ Next Game │ RECRUITING (span 2)` / `Rankings │ Last Game │ Player Scoring │ News`. Locker Room leads so Next Game sits directly above Last Game.

### Walk-On Welcome

Season-start reveal of the walk-ons who joined the roster, shown on the first FCC landing of a new season (week 1, before Training Camp). Season 2+ only.

- `topData.walk_on_welcome_modal.eligible`
- Rendered by `window.WalkOnWelcomeModal` (`js/shared/walkOnWelcomeModal.js`)
- Dismissed via `PATCH /franchise/walk-on-welcome-modal-seen`
- Registered in `fccHasCompetingModal()` so archetype-evolution yields to it

Cannot collide with **Cut Players Required** — that needs training complete for week 1, which the rollover leaves false.

Every season (including season 1, which gets no modal) also writes a **"{Team} Walk Ons Announced"** news story carrying the same table. Full rules: [Season_Init_System.md](Season_Init_System.md) → Walk-On Announcement.

---

## FCC Page Load

FCC uses a full-screen `#page-load-overlay` during initial document load. The
overlay is part of the page HTML and is visible before the JavaScript controller
finishes fetching live data.

The frontend may restore cached FCC data from `sessionStorage` during init. This
cached render is a warm paint only:

- it can populate the shell and cards behind the overlay
- it must not be shown as current data before the authoritative load completes
- `#page-load-overlay` remains visible until `/franchise/command-center/data`
  has returned and the current top shell / CTA / home basics have rendered

This avoids the stale-data flash where users briefly saw previous-week or
previous-state FCC content for 1-3 seconds while fresh data loaded.

After authoritative top data returns:

1. FCC compares cached week to fresh week.
2. Week-sensitive home caches are invalidated if the week changed.
3. fresh top data becomes `commandCenterTopDataCache`.
4. shell buttons, Inbox, recruits, modal gates, roster/standings, and home-card
   dependencies continue hydrating.
5. the overlay is hidden by the existing final page-load cleanup.

In-page tab switches do not show the full-page overlay. Individual tabs may show
local loading states while their lazy data fetches resolve.

---

## Data Wiring

## Core frontend state

Key FCC state variables in the controller:

- `franchiseId`
- `userTeamId`
- `userTeamNameForLeaders`
- `userConference`
- `userRegion`
- `commandCenterTopDataCache`
- `standingsDataCache`
- `teamData`
- `userRosterPlayersCache`
- `userScheduleDataCache`
- `homeLastGameDataCache`
- `leadersDataCache`
- `fccTeamStatsSummaryCache`
- `fccPlaybooksSummaryCache`
- `leanRecruitsDataCache`
- `signedRecruitsDataCache`

### Session cache

FCC persists a shell-level session cache in `sessionStorage` under:

- `fcc-shell:{franchiseId}:{teamId|unknown}`

Cached payload includes:

- top data
- standings data
- roster players
- team data
- schedule data
- last-game data
- opponent rosters

Week-sensitive home caches are invalidated when the cached week differs from the freshly loaded week.

The session cache is not authoritative. It is used for behind-the-overlay warm
rendering and fast tab rehydration, then refreshed from live endpoints.

---

## Primary endpoints used by FCC

### Top shell / lifecycle payload

- `GET /franchise/command-center/data?franchise_id=...&profile=1`

This is the most important FCC payload.

Current response fields used by FCC include:

- `team`
- `team_id`
- `current_season`
- `week`
- `rank`
- `prestige`
- `primary_color`
- `user_conference`
- `user_region`
- `rankings`
- `next_game_summary`
- `last_game_summary`
- `training_completed`
- `session_type`
- `cut_required`
- `cut_count`
- `current_recruiting_results_week`
- `lean_recruits`
- `team_name_map`
- `week_35_user_recruits`
- `last_training_report_week`
- `season_inbox`
- `news_headlines`
- `eos_tournament_active`
- `conference_tournaments`
- `region_tournaments`
- `national_tournament`
- `eos_tournament`
- `pending_championship_moments`
- `training_disabled_for_eos`
- `training_disabled_for_postseason`
- `eog_team_attrs_frozen_for_postseason`
- `user_eliminated`
- `offer_sim_rest`

### Team / roster / gameplay support

- `GET /franchise/team-data?franchise_id=...&team_id=...`
- `GET /api/gameplan?mode=franchise&franchise_id=...&team_id=...`
- `GET /roster/{team_id}?franchise_id=...&profile=1`
- `GET /franchise/state?franchise_id=...&profile=1`

### Standings / schedule / leaders / stats

- `GET /franchise/standings?franchise_id=...&scope=user_region&team_id=...&profile=1`
- `GET /franchise/schedule?franchise_id=...&user_team_only=1`
- `GET /franchise/leaders?franchise_id=...&scope=season&view_scope=conference&limit=5`
- `GET /franchise/team-stats?franchise_id=...&scope=conference`

### Scouting

- `POST /franchise/play-next-game`
- `GET /franchise/team-data?franchise_id=...&team_name={opponent}`
- `GET /franchise/scouting-report?franchise_id=...&team_name={opponent}`

### CTA flows

- `POST /franchise/play-next-game`
- `POST /franchise/sim-rest-of-tournament`
- `POST /franchise/sim-championship`
- `POST /franchise/finish-season`

### Recruiting

- routed pages used from FCC:
  - `recruiting-results.html`
  - `recruiting-orders.html`

---

## Navigation / Return Rules

FCC uses:

- `tab=...` style local tab state via shared command-center tab manager
- `return_url` on routed pages to preserve return position

Direct routed destinations commonly include:

- `training.html`
- `set-lineup.html`
- `cut-players.html`
- `game-plan.html`
- `playbooks.html`
- `training-report.html`
- `box-score.html`
- `recruiting-results.html`
- `recruiting-orders.html`
- standalone stats/standings/schedule/leaders/recruiting pages

FCC refreshes outbound links from the current page state so returning users can land back in the correct FCC context.

---

## Live vs Legacy / Unreferenced FCC Code

The FCC implementation contains both active modern behavior and some leftover hooks from older versions.

### Live modern behavior

Documented above:

- current tab bar
- Coach’s Office
- local scouting tab
- local schedule tab
- inbox persistence
- EOS bracket rendering
- hero CTA state machine

### Legacy / partially unreferenced pieces still in the code

These exist and should not be confused with the current live FCC surface:

- references to a `Resources` link/button set
- references to `#set-gameplan-franchise`
- references to `#playbooks-franchise`
- recruiting button/live-copy hooks that may outlive the current top-right hero markup
- old modal scouting button hook `#scouting-report-btn`
- placeholder / older renderer functions for stats, rankings, team traits, recruits, training results, and team report variants that are not the main modern FCC path
- disabled dev-only regular-season sim popup block

Documentation rule:

- FCC.md should describe the **live FCC first**
- legacy hooks should only be mentioned as technical-debt / cleanup context

---

## API Load / Optimization Context

FCC is materially heavier than a simple command-center shell. The current page can perform a meaningful number of fetches even before the user explores deeper tabs.

### Initial-load pressure points

Typical modern FCC init does all or most of the following:

1. `/franchise/command-center/data`
2. `/franchise/team-data` for chemistry alignment
3. `/roster/{team_id}` + `/franchise/state` via `RosterLoader`
4. `/franchise/standings`
5. `/franchise/team-data` again inside `loadTeamData()`
6. `/api/gameplan`
7. `/roster/{team_id}` again inside `loadTeamData()` for players
8. `/api/auth/me` for display-color preference
9. later, on tab open:
   - `/franchise/schedule`
   - `/franchise/leaders`
   - `/franchise/team-stats`
   - `/api/playbooks`
   - scouting fetches

### Known duplicate / near-duplicate work

- `/franchise/team-data` is fetched early for chemistry and again in `loadTeamData()`
- `/roster/{team_id}` is loaded through `RosterLoader` and then separately again inside `loadTeamData()`
- `/franchise/command-center/data` is refetched in some CTA flows
- tournament bracket rendering does an extra `/franchise/team-stats` fetch for team-name mapping

### Existing optimization mechanisms

- `sessionStorage` shell cache
- in-memory tab caches
- week-sensitive cache invalidation
- lazy hydration on tab show for:
  - Playbooks
  - Scouting Report
  - Schedule
  - Team Stats
  - Leaders
  - Inbox

### Practical optimization targets

Future FCC optimization work should likely focus on:

1. collapsing duplicate roster/team-data fetches
2. reducing repeated top-data fetches inside CTA handlers
3. pushing more summary data into `/franchise/command-center/data` when it clearly reduces duplicate calls
4. separating truly required shell data from deeper-tab data
5. preserving the current fast-return cache behavior while trimming redundant network requests

---

## Implementation Summary

If you need to reorient quickly in another thread:

1. start with `/franchise/command-center/data`
2. confirm `franchise_id` and resolved `userTeamId`
3. check `updatePlayButton(topData)` for lifecycle state
4. check `CommandCenterTabs.initCommandCenterTabs(...)` for tab-show behavior
5. check `loadTeamData()`, `ensureHomeScheduleData()`, `renderFccPlaybooksSummary()`, `renderScoutingTab()`, and `renderFccInbox()` for the active secondary systems
6. treat older resources/button hooks as legacy until proven otherwise by live HTML
