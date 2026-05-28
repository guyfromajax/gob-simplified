# FTE Tutorial Game — Initial State Injection Spec

**Purpose:** A complete data shopping list for booting the tutorial game engine into "Q4, 4:00 remaining, 60-60." Everything the engine needs to start mid-game is listed below. Coach fills in the `[INPUT]` cells; `[FIXED]` and `[DEFAULT]` sections are noted for transparency but require no action.

**Audience:** James to fill in. Then Claude implements `init_game` extension + tutorial roster fabrication.

---

## How to read this doc

| Tag | Meaning |
|---|---|
| `[FIXED]` | Locked tutorial constant. Don't change unless you're rewriting the spec. |
| `[INPUT]` | Coach fills this in. |
| `[DEFAULT]` | Safe default suggested; override only if you want different behavior. |

---

## 1. Game-level state

| Field | Value | Tag | Notes |
|---|---|---|---|
| `quarter` | `4` | [FIXED] | Q4. |
| `time_remaining` | `240` (seconds) | [FIXED] | 4:00 left. |
| `clock` | `"4:00"` | [FIXED] | Display mirror of `time_remaining`. |
| `shot_clock_remaining` | `30` | [FIXED] | Full shot clock at boot. |
| `score` | `{user_team: 60, opponent: 60}` | [FIXED] | Tied 60-60. |
| `offensive_state` | `"HCO"` | [FIXED] | Half-court offense (vs FAST_BREAK, FCP, HCT). Note: SIP is a *turn type*, not an offensive_state — see "First turn type" below. |
| First turn type | `SIP` (Side Inbound Pass) | [FIXED] | Tutorial boots in a post-timeout state. Engine emits a SIP turn via the existing timeout-resume path ([BackEnd/main.py:381-407](BackEnd/main.py#L381-L407)), then transitions to HCO. No new turn-emission machinery. |
| `current_playcall` | `""` | [DEFAULT] | Empty → engine picks. |
| `defense_playcall` | `""` | [FIXED] | Empty → engine picks (per Coach instruction). |
| `mode` | `"tutorial"` | [FIXED] | New value (extends `single` / `franchise` / `tournament`). Gates all tutorial-only branches. |
| `game_stats_initialized` | `true` | [FIXED] | Critical — prevents engine from zeroing the pre-fab stats on first turn. |
| `franchise_id` | `null` | [FIXED] | No franchise touched. |
| `tournament_id` | `null` | [FIXED] | No tournament touched. |
| `game_id` | auto-generated | [FIXED] | Deleted post-game via `/api/games/delete-completed-single` precedent. |

### Opening possession of Q4

| Field | Value | Tag |
|---|---|---|
| `offense_team` | **user team** | [FIXED] | User has the ball coming out of the timeout. |

---

## 2. Per-team state

These apply to both the user team and the opponent.

| Field | User team | Opponent | Tag | Notes |
|---|---|---|---|---|
| `team_fouls` (Q4 fouls only — resets per quarter) | `3` | `3` | [FIXED] | Range 0-5+; ≥5 triggers bonus. Both teams 2 fouls away from bonus. |
| `timeouts` (remaining) | `1` | `1` | [FIXED] | Max 4 at game start. Both teams down to last timeout. Note: the SIP-turn "timeout" the user comes out of does NOT decrement these (it's a synthetic stoppage for set-lineup, not a real timeout). |
| Home/Away assignment | **home** | away | [FIXED] | User is home. |
| `home_crowd_factor` | applies to user (home) | | `4` | [FIXED] | 1-5; user gets the +crowd boost. |
| `strategy_settings` | all keys = `2`, except `fc_press` = `1`, `hc_trap` = `1` | same | [FIXED] | Overrides standard random init. Applied via `body.strategy_settings` per existing override mechanism. |
| `strategy_calls` | all `None` | all `None` | [DEFAULT] | |
| `scouting_data` | `{}` | `{}` | [DEFAULT] | |
| `plays` | standard universal playbook | standard universal playbook | [DEFAULT] | Loaded via `_init_plays_from_universal()`. |

---

## 3. Opponent nerf (shot_threshold override)

Per Q6 of the design review. Aligned to the recalibrated 10-210 scale.

| Field | Value | Tag | Notes |
|---|---|---|---|
| Computer team `shot_threshold` | `210` | [FIXED] | Max of the new scale → forced miss for opponent. |
| User team `shot_threshold` | `10` | [FIXED] | Min of the new scale → forced make for user. |

> **Engineering note:** `init_team_attributes` currently rolls `shot_threshold` randomly inside the 10-210 range. We'll add an optional `shot_threshold_override` parameter that's set only when `mode === "tutorial"`. All other team_attributes (`discipline`, `fight`, `rebound_modifier`, `offensive_efficiency`, `team_chemistry`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`) initialize per the standard process.
>
> **Known engine inconsistency (out of scope for this PR):** the balancing logic in [phase_resolution.py:3601](BackEnd/engine/phase_resolution.py#L3601) and [:3605](BackEnd/engine/phase_resolution.py#L3605) still uses the **old-scale** values `-10` (forced make) and `190` (forced miss). Same in the fast-break overrides in [rim_runner_fast_break.py](BackEnd/engine/rim_runner_fast_break.py). These should be migrated to `10` / `210` in a separate ticket so the tutorial PR doesn't change balancing behavior for existing single/franchise/tournament games.

---

## 4. Per-quarter score breakdown (`points_by_quarter`)

The scoreboard needs Q1 / Q2 / Q3 numbers that **sum to 60 each** so the displayed quarter-by-quarter row is coherent when the user opens box-score-style views. (Even though there's no Box Score button on the tutorial post-game modal, this still renders on the in-game scoreboard.)

| Quarter | User team | Opponent | Tag |
|---|---|---|---|
| Q1 | `[INPUT: 14]` | `[INPUT: 18]` | [INPUT/DEFAULT] |
| Q2 | `[INPUT: 18]` | `[INPUT: 15]` | [INPUT/DEFAULT] |
| Q3 | `[INPUT: 28]` | `[INPUT: 27]` | [INPUT/DEFAULT] |
| Q4 | 0 | 0 | [FIXED] |
| **Total entering Q4** | **60** | **60** | [FIXED] |

> Defaults above tell a small story: user trailed early, fought back in Q3, now tied entering the final 4 minutes. Replace with any distribution you like — must sum to 60 / 60.

---

## 5. Per-team starting-five stat lines (for set-lineup stats tab + engine continuity)

The set-lineup screen's **stats tab** must render coherent box-score-style numbers for each starter that ladder believably to the team's Q1-Q3 totals above. The engine will also use these as the persisted `player.stats["game"]` so they appear on the scoreboard if the user hovers / drills in during play.

### Stat fields per player

| Field | Type | Notes |
|---|---|---|
| `PTS` | int | Points scored Q1-Q3. |
| `REB` | int | Total rebounds (OREB + DREB). |
| `AST` | int | Assists. |
| `STL` | int | Steals. |
| `BLK` | int | Blocks. |
| `TO` | int | Turnovers. |
| `FGM/FGA` | "x/y" | Field goals made / attempted (all shots including 3s). |
| `3PM/3PA` | "x/y" | 3-point makes / attempts. (3PA ⊆ FGA.) |
| `FTM/FTA` | "x/y" | Free throws. |
| `F` | int | Personal fouls. **Keep ≤2 for all starters** to avoid foul trouble in Q4. |
| `MIN` | int | Minutes played (Q1-Q3 = 36 game-minutes max). |

### Bench players

Same fields, smaller numbers (or 0s if you want to keep them on the pine). 5-7 bench rows per team typical. Bench `MIN` + starter `MIN` should roughly cover the rotation; engine doesn't strictly enforce this but it shows on stat drilldowns.

### Team blocks to fill

Nine blocks total: each of the 8 user-selectable teams + Xavien (since Xavien is always the opponent except when the user picks Xavien themselves, in which case South Lancaster from the user-team block doubles as opponent stats).

For each team, list the starter at each position and fill the row.

---

#### 5.1 Bentley-Truman ("Top-Shelf Talent")

**Starters**

| Pos | Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PG | Xenon Fletcher |  |  |  |  |  |  |  |  |  |  |  |
| SG | Trent Athens |  |  |  |  |  |  |  |  |  |  |  |
| SF | Ronnie Rozier |  |  |  |  |  |  |  |  |  |  |  |
| PF | CJ Castleman |  |  |  |  |  |  |  |  |  |  |  |
| C  | Kermit Prospect |  |  |  |  |  |  |  |  |  |  |  |

**Bench** (5-7 rows, add as needed)

| Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _____ |  |  |  |  |  |  |  |  |  |  |  |

---

#### 5.2 Lancaster ("Muscle & Defense")

**Starters**

| Pos | Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PG | Ervin Miller |  |  |  |  |  |  |  |  |  |  |  |
| SG | Norris Khan |  |  |  |  |  |  |  |  |  |  |  |
| SF | Wilbert Struthers |  |  |  |  |  |  |  |  |  |  |  |
| PF | Cedric Buckles |  |  |  |  |  |  |  |  |  |  |  |
| C  | Roger Henrich |  |  |  |  |  |  |  |  |  |  |  |

**Bench**

| Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _____ |  |  |  |  |  |  |  |  |  |  |  |

---

#### 5.3 Four Corners ("Hustle & Attitude")

**Starters**

| Pos | Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PG | Josiah Wilson |  |  |  |  |  |  |  |  |  |  |  |
| SG | Jay Giancola |  |  |  |  |  |  |  |  |  |  |  |
| SF | Charles Black |  |  |  |  |  |  |  |  |  |  |  |
| PF | Roberto You |  |  |  |  |  |  |  |  |  |  |  |
| C  | Jeffrey Jackson |  |  |  |  |  |  |  |  |  |  |  |

**Bench**

| Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _____ |  |  |  |  |  |  |  |  |  |  |  |

---

#### 5.4 Ocean City ("Sharpshooters Galore")

**Starters**

| Pos | Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PG | Tommy La |  |  |  |  |  |  |  |  |  |  |  |
| SG | Rupert Holliday |  |  |  |  |  |  |  |  |  |  |  |
| SF | Aaron Mingus |  |  |  |  |  |  |  |  |  |  |  |
| PF | Hector Welke |  |  |  |  |  |  |  |  |  |  |  |
| C  | Jonathan Fabrizio |  |  |  |  |  |  |  |  |  |  |  |

**Bench**

| Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _____ |  |  |  |  |  |  |  |  |  |  |  |

---

#### 5.5 Morristown ("Perfectly Balanced")

**Starters**

| Pos | Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PG | Mose Hawkins |  |  |  |  |  |  |  |  |  |  |  |
| SG | Kevin Nelson |  |  |  |  |  |  |  |  |  |  |  |
| SF | Peter Gregory |  |  |  |  |  |  |  |  |  |  |  |
| PF | Kwame Castor |  |  |  |  |  |  |  |  |  |  |  |
| C  | Carlton Bonner |  |  |  |  |  |  |  |  |  |  |  |

**Bench**

| Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _____ |  |  |  |  |  |  |  |  |  |  |  |

---

#### 5.6 Little York ("Wicked Smart")

**Starters**

| Pos | Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PG | Derrick Smith |  |  |  |  |  |  |  |  |  |  |  |
| SG | AC Buford |  |  |  |  |  |  |  |  |  |  |  |
| SF | Victor Largefoot |  |  |  |  |  |  |  |  |  |  |  |
| PF | Wallace Farrabee |  |  |  |  |  |  |  |  |  |  |  |
| C  | Emery Landraneau |  |  |  |  |  |  |  |  |  |  |  |

**Bench**

| Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _____ |  |  |  |  |  |  |  |  |  |  |  |

---

#### 5.7 Xavien ("Youthful Exuberance") — DEFAULT OPPONENT

**Starters**

| Pos | Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PG | Brian Jeffries |  |  |  |  |  |  |  |  |  |  |  |
| SG | Darnell Love |  |  |  |  |  |  |  |  |  |  |  |
| SF | Marlin McDonough |  |  |  |  |  |  |  |  |  |  |  |
| PF | Scott Swensen  |  |  |  |  |  |  |  |  |  |  |  |
| C  | Antoine Ellington |  |  |  |  |  |  |  |  |  |  |  |

**Bench**

| Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _____ |  |  |  |  |  |  |  |  |  |  |  |

> Xavien stats apply when user picks any of the other 7 teams.

---

#### 5.8 South Lancaster ("Us vs The World") — DOUBLES AS OPPONENT WHEN USER PICKS XAVIEN

**Starters**

| Pos | Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PG | Ferdinand Steele |  |  |  |  |  |  |  |  |  |  |  |
| SG | Felix Steele |  |  |  |  |  |  |  |  |  |  |  |
| SF | Tyrone Celaya |  |  |  |  |  |  |  |  |  |  |  |
| PF | Terry Axelford |  |  |  |  |  |  |  |  |  |  |  |
| C  | Neel Baldwin |  |  |  |  |  |  |  |  |  |  |  |

**Bench**

| Player | PTS | REB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _____ |  |  |  |  |  |  |  |  |  |  |  |

---

### Coherence checks (per team)

When filling in stats, the totals should roughly satisfy:

- `sum(PTS across all players) === team's Q1+Q2+Q3 from Section 4`
- `sum(FGM × 2) + sum(3PM × 1 extra) + sum(FTM) === sum(PTS)` (a 3PM also counts as 1 FGM, so it's worth 2+1=3 points)
- `sum(F across all players) ≈ team_fouls accumulated Q1-Q3` (engine resets team_fouls per quarter, but individual `player.metadata["fouls"]` does not reset — so cumulative fouls live on player rows)

---

## 6. Per-player runtime attributes [DEFAULT]

These govern in-game dynamics. Mid-Q4 defaults:

| Field | Starters | Bench | Notes |
|---|---|---|---|
| `NG` (energy) | `0.95` | `0.95` | Per Coach: all players boot at 0.95. Engine decrements per turn. |
| `MO` (momentum) | `0` | `0` | Neutral entering Q4. |
| `CH` (character) | random 1-100 | random 1-100 | Standard `randomize_game_attributes()`. |
| `EM` (emotion) | random 1-100 | random 1-100 | Standard `randomize_game_attributes()`. |
| `player.metadata["fouls"]` | taken from Section 5 `F` column | from Section 5 `F` column | **Does not reset per quarter** — accumulates whole game. |

Core attributes (`SC`, `SH`, `ID`, `OD`, `PS`, `BH`, `RB`, `ST`, `AG`, `ND`, `IQ`, `FT`) come from the canonical player document in the players collection. No tutorial-specific overrides.

---

## 7. Optional/safe-to-omit state [DEFAULT]

The following game_state fields are left at engine defaults. Listed for transparency; **no input needed**:

`shooter`, `free_throws`, `free_throws_remaining`, `one_and_one`, `no_defender_shots`, `no_defender_shots_breakdown`, `last_ball_handler`, `last_rebounder`, `last_rebound`, `last_stealer`, `last_turnover_player`, `foul_team`, `foul_type`, `foul_player`, `man_defense_matchups`, `man_defense_matchups_computer`, `rim_runner_by_team_id`, `opening_tip_winner`, `opening_lineup`, `computer_timeouts`, `home_crowd_away_shot_threshold_delta`, `home_crowd_home_shot_threshold_delta`.

---

## 8. Engineering work this implies (for Claude, not for Coach)

1. **`init_game` extension** — accept an optional `tutorial_initial_state` payload that, when present and `mode === "tutorial"`, bypasses the standard 0-0 / Q1 boot and writes the values above directly into `game_state`, `team.team_attributes`, and per-player rows.
2. **`init_team_attributes` extension** — accept optional `shot_threshold_override` per team; applied only when `mode === "tutorial"`.
3. **Pre-fab roster** — a `BackEnd/data/tutorial_rosters.py` (or similar) file holds the 9 stat blocks from Section 5 as Python dicts, keyed by team name. Loaded at boot, written into `player.stats["game"]` and `player.metadata["fouls"]`.
4. **`game_stats_initialized: true`** must be set before the first turn, or the engine will zero everything fabricated.
5. **No franchise / tournament writes** — `mode === "tutorial"` follows the existing `single` path through `finalizeGame.js` (no `franchise/complete-week`, no `tournament/save-result`), and the game doc is deleted via `delete-completed-single` precedent after the post-game modal closes.

---

## Open items / parking lot

| # | Item | Decision needed from Coach |
|---|---|---|
| O1 | Section 1: opening possession (user or opponent?) | Suggest opponent. | Answer: user
| O2 | Section 2: user = home or away? | Suggest home. |  Answer: home
| O3 | Section 2: home_crowd_factor (1-5)? | Suggest 4. |  Answer: 4
| O4 | Section 4: per-quarter splits (default = [14/18, 18/15, 28/27])? | Override or accept. |  Answer: accept
| O5 | Section 5: all 9 stat blocks | Fill at your desired fidelity. | Answer: see below for player stats template
| O6 | Bench depth per team — 5? 7? | Tell me how many bench rows you want; I'll add rows. |  Answer: see above for starting 5, stack rank the backups according to their RT value


**Player Stats**
Note any stats not accounted for below (like DEFA, DEF%, etc) will be 0

**User Team Player Stats**
| Pos | Player | PTS | OREB | DREB | TREB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
Starting PG | 9 | 0 | 1 | 1 | 6 | 3 | 0 | 8 | 4/10 | 1/3 | 0/2 | 2 | 21
Starting SG | 14 | 1 | 4 | 5 | 3 | 6 | 2 | 0 | 5/11 | 0/4 | 4/4 | 1 | 24
Starting SF | 17 | 2 | 6 | 8 | 3 | 0 | 0 | 3 | 6/8 | 1/1 | 4/5 | 2 | 20
Starting PF | 2 | 5 | 4 | 9 | 0 | 0 | 0 | 0 | 1/5 | 0/1 | 0/0 | 0 | 21
Starting C | 9 | 2 | 9 | 11 | 0 | 1 | 3 | 1 | 2/8 | 0/0 | 5/6 | 2 | 19
Backup 1 | 5 | 0 | 1 | 1 | 5 | 1 | 0 | 5 | 1/3 | 0/1 | 3/3 | 1 | 12
Backup 2 | 3 | 0 | 5 | 5 | 1 | 1 | 0 | 3 | 1/4 | 1/1 | 0/4 | 1 | 11
Backup 3 | 1 | 0 | 4 | 4 | 0 | 0 | 1 | 0 | 0/2 | 0/0 | 1/2 | 2 | 8
Backup 4 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0/1 | 0/1 | 0/0 | 0 | 4
Backup 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0
Backup 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0
Backup 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0


**Computer Team Player Stats**
| Pos | Player | PTS | OREB | DREB | TREB | AST | STL | BLK | TO | FGM/FGA | 3PM/3PA | FTM/FTA | F | MIN |
Starting PG | 5 | 0 | 2 | 2 | 10 | 2 | 0 | 4 | 2/3 | 1/3 | 0/2 | 1 | 21
Starting SG | 20 | 1 | 4 | 5 | 3 | 6 | 2 | 4 | 7/14 | 2/5 | 4/7 | 1 | 23
Starting SF | 3 | 0 | 5 | 5 | 5 | 0 | 0 | 2 | 1/9 | 1/3 | 0/1 | 0 | 23
Starting PF | 11 | 1 | 2 | 3 | 0 | 1 | 0 | 0 | 4/7 | 0/0 | 3/3 | 3 | 18
Starting C | 16 | 1 | 7 | 8 | 0 | 1 | 3 | 0 | 6/9 | 0/0 | 4/4 | 3 | 16
Backup 1 | 0 | 0 | 1 | 1 | 5 | 1 | 0 | 0 | 0/5 | 0/1 | 0/4 | 1 | 12
Backup 2 | 3 | 0 | 5 | 5 | 1 | 1 | 0 | 4 | 1/4 | 0/0 | 1/1 | 1 | 11
Backup 3 | 2 | 0 | 4 | 4 | 0 | 0 | 1 | 0 | 1/1 | 0/0 | 0/4 | 2 | 8
Backup 4 | 0 | 0 | 3 | 3 | 0 | 0 | 1 | 2 | 0/1 | 0/1 | 0/0 | 0 | 5
Backup 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 | 3
Backup 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0
Backup 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0
