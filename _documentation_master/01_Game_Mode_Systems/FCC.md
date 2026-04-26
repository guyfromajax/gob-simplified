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

Possible live states:

- `Run Training`
- `Run Training Camp`
- `Play Next Game`
- `Cut Players`
- `Recruiting`
- `Go To Next Season`
- `Sim Next Round`

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

### EOS-specific behavior

The CTA logic depends on:

- `eos_tournament_active`
- `eos_tournament.completed`
- `training_disabled_for_eos`
- `user_eliminated`
- `offer_sim_rest`
- `cut_required`
- `week`

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
12. `Press`
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
  - opponent record
  - opponent rank
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

- currently placeholder
- live text: `In Development`

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

It displays human-readable interpretations of strategy sliders for:

- Offense
- Defense
- Inside
- Aggression
- Attack
- Half-Court Trap
- Outside
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

---

## Scouting Report Tab

The `Scouting Report` tab replaces the old modal-style scouting flow with an embedded tab view.

It renders:

1. upcoming opponent summary
2. projected starting five
3. opponent Team Measures
4. opponent Play Usage (Last Game)

### Opponent resolution

FCC resolves the upcoming opponent by:

1. reading top data / EOS state
2. calling `/franchise/play-next-game`
3. comparing the returned matchup to the user team

### Opponent data fetches

When the tab opens, FCC loads:

- `/franchise/team-data?franchise_id=...&team_name={opponent}`
- `/franchise/scouting-report?franchise_id=...&team_name={opponent}`

The opponent summary also uses:

- standings cache
- rankings cache

Current summary fields:

- opponent name
- opponent record
- opponent national rank

Important note:

- legacy `#scouting-report-btn` modal behavior is explicitly removed by `disableLegacyFccScoutingModal()`

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

- `leadersDataCache`

Footer link:

- routes to standalone `leaders.html`

---

## Press Tab

Current state:

- placeholder only
- body text: `In Development`

No active data load is attached to this tab today.

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

- the current HTML shell no longer exposes the hero recruiting button elements in the visible markup chunk used by the modern hero
- the JS still contains `updateRecruitingButton(...)` logic keyed to `#fcc-recruiting-btn` and `#fcc-recruiting-live-copy`
- this is part of the live/legacy split that should be cleaned up carefully in future FCC passes

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
- hero CTA may become `Sim Next Round`
- champion completion can trigger championship summary modal

---

## Championship / Season-End Modals

FCC currently owns several modal flows:

### Championship Complete

Shown when `topData.championship_summary` exists and the result has not already been marked seen in localStorage.

Actions:

- `Box Score`
- `Back To Locker Room`

### Cut Players Required

Shown when:

- `topData.cut_required`
- `topData.cut_count > 0`

### Go To Next Season

Confirmation modal shown before calling:

- `/franchise/finish-season`

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

- `fcc-shell:{franchiseId}`

Cached payload includes:

- top data
- standings data
- roster players
- team data
- schedule data
- last-game data
- opponent rosters

Week-sensitive home caches are invalidated when the cached week differs from the freshly loaded week.

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
- `eos_tournament_active`
- `conference_tournaments`
- `region_tournaments`
- `national_tournament`
- `eos_tournament`
- `championship_summary`
- `training_disabled_for_eos`
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
