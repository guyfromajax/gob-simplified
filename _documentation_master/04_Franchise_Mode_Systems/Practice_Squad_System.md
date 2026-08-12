# Practice Squad System (**verified 2026-06-13**)

> Verified vs `franchise_routes.py`, `franchise_manager.py`, `api.py`, `franchise-command-center.js` — **architecture, data model, lifecycle, CH progression bands, week-35 cut odds, and roster invariants all match code.** `api.py` anchors (`get_team_roster` 5304, walk-on gate 5491, `training_squad` array 5530) still accurate. **Fixed:** every `franchise_routes.py` / `franchise_manager.py` / `franchise-command-center.js` line number had drifted and was refreshed to current locations.

> **Terminology:** the user-facing label and the data field are **"Training Squad"**
> (`training_squad_players`). "Practice Squad" / "PS" appear in some early design
> notes and are synonyms for the same concept. Prefer **Training Squad** in code,
> UI copy, and new docs.

## 1. What it is (rationale)

Every franchise team carries a **15-man roster** split into:
- **Active roster — 12 players** (`ftd.players`): eligible to play, appear in lineups/sims/stats.
- **Training Squad — 3 players** (`ftd.training_squad_players`): **ineligible to play**, no
  season stats, retained on the roster. They develop in the background and rejoin the
  active pool to compete again at the next Training Camp.

Goals:
- Give every roster depth + a development pipeline instead of hard-cutting players each season.
- Players are **not deleted** at Training Camp — they move to the Training Squad. (Real
  deletion only happens at the optional **week-35 pre-recruiting cut**; see §6.)
- Surface squad development to the user via periodic in-season reports.

**Roster invariants** (hold for every team after Training Camp, every season):
`active (players) == 12`, `training squad == 3`, `total == 15`, no overlap between the two lists.

A read-only checker exists: `scripts/inspect_franchise_roster_counts.py` (flags `total>15`,
`active>12`, overlap, and prints walk-on counts + class-year spread).

## 2. Data model

Per-team state lives on **FTD** (`franchise_team_data`):

| Field | Meaning |
|---|---|
| `players` | active roster (12 after camp) — the ONLY playable list |
| `training_squad_players` | training-squad ids (3 after camp) — **separate** list, NOT a subset of `players` |
| `scholarship_players` | scholarship subset of active |
| `playing_time_promise_players` | PTP subset of active |

Per-player attributes live on **FPD** (`franchise_players_data`), `attributes` + `anchor_*`
mirror, `meta.archetype` (`"Walk On"` for walk-ons), `meta.year`.

Per-franchise report state lives on the **franchise doc**:

| Field | Meaning |
|---|---|
| `training_squad_reports` | `{ "<week>": {week, players:[{player_id,name,pos,baseline,current}]} }` |
| `training_squad_report_baseline` | rolling `{player_id: {attr:val}}` snapshot = values at the last report (or post-camp) |
| `season_inbox` | report links pushed here as `{type:"training_squad_report", week, message}` |

**Key design rule:** anything that treats `players` as the playable roster keeps working
unchanged — training-squad players are a separate list, never in `players`.

## 3. Lifecycle (per season)

```
Season init ─► 12 base + 3 generated walk-ons = 15 (all in `players`, TS empty)
   │
Week 1 Training Camp ─► assign 3 to Training Squad ─► 12 active + 3 TS
   │   (user picks via modal; CPU auto-picks lowest RT)
Weeks 2–26 ─► each completed week, every TS player's 13 attrs evolve (CH-gated)
   │   reports published after wk 6/11/16/21/26 games (user team only)
Week 35 "Run Recruiting" ─► optional REAL cut (user) + CPU RT-based cuts ─► recruiting
   │
Season rollover ─► non-graduating active + non-graduating TS both return to the pool,
                   + signed recruits + walk-on fill ─► 15 ─► next Training Camp trims to 12+3
```

## 4. Walk-on generation

`generate_walk_on_profile()` — `BackEnd/models/franchise_manager.py:182`. Shared by season-1
init and the week-35 roster fill. Low/small Freshman; attrs roll **1–32** with **≤3 over 29**;
height 66–72"; `archetype="Walk On"`; **CH init `randint(1,90)`** (other ranges from
`randomize_game_attributes`).

- **Season 1:** `initialize_season` generates **3 walk-ons per team (all 128)** during
  franchise creation (under the load screen), → 15-man rosters. `franchise_manager.py:380`.
  FTD `training_squad_players` starts `[]` (assigned at camp). `franchise_manager.py:617`.
- **Season 2+:** the week-35 signings backfill to 15 with recruits then walk-ons (existing flow).

## 5. Training Camp → Training Squad (all seasons)

Players are **moved**, not cut/deleted (FPD retained).

- **User** — `POST /franchise/cut-players` → `cut_franchise_players` (`franchise_routes.py:9865`).
  Requires exactly 3 → TS, leaving 12 active. Drives the cut-players page in its **default
  (assignment) mode**.
- **CPU** — `_apply_cpu_training_camp_cuts` (`franchise_routes.py:8291`): lowest-RT 3 → TS.
  Tiebreak `_choose_cut_player_ids`: lowest RT, then cut the most-senior class first
  (keep youth), then random. Excludes the user's team.
- **Requirement signal** — `_week_1_cut_requirement` (`franchise_routes.py:8267`): `cut_count =
  roster_count - 12`; surfaces `cut_required`/`cut_count` to the FCC, which shows the modal +
  "Assign Training Squad" button.

### UI sequencing (season-1 week-1 return)
The **Team Attributes tutorial** must appear before the Training-Squad assignment modal. The
FCC defers the TS modal via `GOBTutorialAlerts.whenReturnAlertsSettled()` — it fires once the
tutorial alert is dismissed (or immediately if no tutorial shows; 8s safety fallback).
See `Tutorial_Alerts_System.md`.

## 6. In-Season Progression & Reporting

`_apply_training_squad_progression_and_report()` — `franchise_routes.py:8377`, called once per
completed week from `_finalize_franchise_week_after_cpu_games` (`franchise_routes.py:4087`).

**Progression (weeks 2–26, USER + ALL CPU teams; persisted to FPD):**
- Each Training-Squad player's **13 attributes** evolve: `SC SH ID OD PS BH RB AG ST ND IQ FT CH`.
- Per-week delta is **CH-gated** and weighted (`_ts_progression_delta`, `BackEnd/api/franchise_routes.py`):

  | CH | weekly attr delta weights |
  |---|---|
  | >79 | -2: 10, -1: 20, 0: 20, 1: 30, 2: 10 |
  | >59 | -2: 20, -1: 20, 0: 30, 1: 20, 2: 10 |
  | >39 | -2: 20, -1: 30, 0: 20, 1: 20, 2: 10 |
  | >19 | -2: 30, -1: 20, 0: 20, 1: 20, 2: 10 |
  | else | -2: 40, -1: 20, 0: 20, 1: 10, 2: 10 |

  The implementation uses the listed values as relative weights. Each attr rolls independently. CH itself evolves, but the CH bucket is selected once per player/week from current CH before that week's 13 attr rolls.
- Clamp `PLAYER_ATTR_CLAMP = (1, None)` (min 1, no max). Updates both `attr` and `anchor_attr`.
- `position_ratings` recomputed after evolving (so RT reflects development; cuts/display stay accurate).
- Starts **week 2** (TS players already evolved via Training Camp in week 1).

**Reports (USER team only; after wk 6/11/16/21/26 games):**
- Baseline captured pre-progression on the first run (post-camp values) → `training_squad_report_baseline`.
- Each report = **delta vs the previous report** (wk6 vs post-camp; wk11 vs wk6; …). After
  building, baseline resets to current.
- Stored in `franchise_doc.training_squad_reports["<week>"]` with per-player `{baseline, current}`.
- Inbox entry pushed: `"Week #{n} Training Squad Development report"`.
- Served by `GET /franchise/training-squad-reports` (`franchise_routes.py:10062`), newest week first.

### Report page
`FrontEnd/static/training-squad-report.html` + `training-squad-report.js`. Reports **stacked
newest-first** with separators; each block has a **Changes ⇄ Absolute** toggle (mirrors the
training report's Player Changes section). Linked from the FCC Inbox (`renderFccInbox`,
`franchise-command-center.js:3917`).

## 7. Week-35 Cuts (real, FPD-deleting)

Distinct from Training-Squad assignment: these **permanently delete** players (FPD removed +
stripped from all FTD lists) to open better recruiting slots.

- **Trigger:** week-35 "Run Recruiting" button shows a modal — *"Would you like to cut any
  players ahead of recruiting?…"* / **Cut Players** | **No Cuts** (`franchise-command-center.js:3659`).
  - **No Cuts** → recruiting-orders page.
  - **Cut Players** → `cut-players.html?mode=cut` → on submit → recruiting-orders page.
- **User cut page (`mode=cut`)** — `cut-players.js` `isCutMode`: shows **active + training squad**,
  allows **any number incl. 0**, posts to `POST /franchise/cut-players-final`
  (`cut_franchise_players_final`, `franchise_routes.py:10026`) → `_hard_release_players`
  (`franchise_routes.py:9948`) deletes FPD + strips all FTD lists.
- **CPU cuts** — `_apply_cpu_week_35_cuts` (`franchise_routes.py:9986`), run inside
  `run_week_35_recruiting` (`franchise_routes.py:9520`) **before** `_run_week_35_signings`,
  **regardless of the user's choice**. Per-player best-RT roll over **active + training squad**:
  RT<10 → 100% cut, RT<15 → 50%, RT<20 → 25%.
- **Refill:** week-35 signings refill every team back to 15 (recruits + walk-on remainder).
  Cuts therefore yield **better recruit slots, not smaller rosters**.

## 8. Season rollover (fold-back)

In the rollover (`franchise_routes.py:12160`, `returning_candidate_ids`), both
**active and training-squad** non-graduating players return to next season's active pool
(advance a year). To keep totals at 15, the recruiting-capacity calcs count returning TS toward
the cap: `_current_team_capacity_state` (`franchise_routes.py:9123`) and
`_calculate_available_roster_spots`. Result: returning actives + returning TS + recruits +
walk-on fill = 15, then Training Camp re-trims to 12 + 3.

## 9. Display

- **`/roster` endpoint** (`BackEnd/api/api.py`) returns a separate **`training_squad`**
  array (attrs, no season stats) alongside the 12 active `players`, plus enriched
  **`projected_starting_five`** (same five + PPG/RPG/APG/DEF% helper as FCC scouting; omitted
  when `tournament_id` is present). Selection is the five autoset would field at tip, not a
  greedy RT fill — see `06_Gameplay_Systems/CPU_Team_Rotation_System.md` §6.
- **FCC Roster tab** — `renderTrainingSquad` (`franchise-command-center.js`) renders a
  "Training Squad" section below the active roster (hidden when empty).
- **Team roster page** (`team-roster-view.html` / `.js`) — **Starting 5** image cards at the
  top (shared `renderProjectedStartingFiveCards`; franchise, base/tutorial, and Practice
  Squad team pages; not tournament). Same "Training Squad" section below the roster.
- **Practice Squad team pages** (`GET /franchise/practice-squad/team`) also return
  `projected_starting_five` enriched from `ps_season_stats`. The PS portrait contract carries
  `portrait_source` plus `image_id`: unsigned FRD recruits use their white recruit master,
  while FPD players use the normal player master. Both retry the existing lazy-paint endpoint
  on a missing generated master, then fall back to `generic_headshot.png`.
- **Walk-on tag** — a transient "(walk on)" name tag shows on the roster only in the new
  season's week-1 preseason (pre-camp) for first-year walk-ons; gated server-side.
  See it drop after Training Camp. (The underlying `meta.archetype="Walk On"`
  persists regardless.)

## 10. Key files

| Area | File:symbol |
|---|---|
| Walk-on generator | `BackEnd/models/franchise_manager.py:182` `generate_walk_on_profile` |
| Season-1 walk-ons | `BackEnd/models/franchise_manager.py:380` (in `initialize_season`) |
| Progression + report | `BackEnd/api/franchise_routes.py` `_apply_training_squad_progression_and_report` |
| CH weighted delta | `BackEnd/api/franchise_routes.py` `_ts_progression_delta` |
| Week-completion hook | `BackEnd/api/franchise_routes.py:4087` `_finalize_franchise_week_after_cpu_games` |
| Camp assignment (user) | `BackEnd/api/franchise_routes.py:9865` `cut_franchise_players` |
| Camp assignment (CPU) | `BackEnd/api/franchise_routes.py:8291` `_apply_cpu_training_camp_cuts` |
| Real cut helper | `BackEnd/api/franchise_routes.py:9948` `_hard_release_players` |
| Week-35 user cut | `BackEnd/api/franchise_routes.py:10026` `cut_franchise_players_final` |
| Week-35 CPU cut | `BackEnd/api/franchise_routes.py:9986` `_apply_cpu_week_35_cuts` |
| Report endpoint | `BackEnd/api/franchise_routes.py:10062` `get_training_squad_reports` |
| Rollover fold-back | `BackEnd/api/franchise_routes.py:12160` `returning_candidate_ids` |
| Capacity (15-cap) | `BackEnd/api/franchise_routes.py:9123` `_current_team_capacity_state` |
| Roster `training_squad` | `BackEnd/api/api.py:5530` (in `get_team_roster`) |
| FCC TS display | `FrontEnd/static/franchise-command-center.js:2247` `renderTrainingSquad` |
| Cut page (dual-mode) | `FrontEnd/static/cut-players.js` (`isCutMode`), `cut-players.html` |
| Week-35 cut modal | `FrontEnd/static/franchise-command-center.js:3659` |
| Report page | `FrontEnd/static/training-squad-report.html` / `training-squad-report.js` |
| Inbox link | `FrontEnd/static/franchise-command-center.js:3917` (`renderFccInbox`) |
| Roster invariant checker | `scripts/inspect_franchise_roster_counts.py` (read-only) |

## 11. Gotchas / notes

- **Don't delete FPD at Training Camp** — only the week-35 path (`_hard_release_players`) deletes.
- **`players` = playable.** Never put TS ids in `players`; lineup/sim/stats read `players`.
- **Capacity must count returning TS** or season-2 overfills past 15.
- **Progression recompute uses the default ("player") position-ratings profile** (matching active
  training). Walk-ons are *generated* with the "recruit" profile, so a walk-on's PF/C rating basis
  shifts slightly the first time progression runs — intended/accepted.
- **Walk-on jerseys** at season-1 init are `null` (walk-ons usually go to TS; TS display needs no number).
- Reports are **user-only**; CPU progression still runs (so CPU TS players are developed when they
  rejoin the pool) but no CPU report is generated.
