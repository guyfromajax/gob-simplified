# End Of Season System (**verified 2026-06-13**)

> Week 35/36 flow + season rollover doc. All-American computation: `BackEnd/utils/all_american.py` (rewritten 2026-10-02; the final is persisted once via `_persist_week_35_awards_if_needed`, stored in the `awards` field); coaching-focus carryover `round(prior × 0.25)` (`carryover_coaching_focus_counts_for_new_season`). **The Week-35 recruiting details below are a summary** — `Recruiting_System.md` is the authoritative source for recruiting mechanics; for the franchise-instance rollover see `Season_Init_System.md`.

## Week 35 Awards And Recruiting

When EOS national week `34` completes, franchise mode advances to week `35`.

### Week 35 Awards

- `Awards` (News › Awards) is live all season: "Projected All-Americans" from week 1, the final at week `35`
- the final is computed once when week `35` begins and never rerolls
- stored on the franchise doc in `awards` (reset at rollover)

### All-American Logic (rewritten 2026-10-02)

All of it lives in `BackEnd/utils/all_american.py`. `franchise_routes.py` only calls it.

| Part | Rule |
|---|---|
| Teams | By listed position. Each team has one PG, SG, SF, PF, C. First team = rank 1 at each position, second = rank 2, third = rank 3. |
| Final third team | Rank 3 or rank 4 per position, by a hash of franchise + season + position (`third_team_rank`). Stable on recompute; never `sim_rng`. Projections always show rank 3. |
| Listed position | The position the roster shows (`leaders_snapshot._roster_position`): CPU teams = best position rating; the user's team = Development Focus training position. No position is stored. |
| Pool | Active roster: FTD `players` minus `training_squad_players`. |
| Score | 0-100 = attributes × wa + stats × ws + team × wt, each component 0-100 within the position. |
| Attributes | FPD `position_ratings[listed position]`, min-max scaled across the position. |
| Stats | Per game (FPD `season`, games = `season.GP`). Each stat = distance above the position average as a share of the leader's distance (average or below = 0, leader = 1). |
| Team | FTD `natl_rank`: rank 1 = 100, last = 0. |
| Weeks | "Week" = regular-season weeks completed. 0 completed = preseason, scored at the week-1 row. |

Timeline:

- Weeks 1-26: the projection is rebuilt once per completed week, on the first command-center (or Awards) read after the advance (`ensure_projection`). It is not in the week-finalize path.
- Week 26: scores and season totals are frozen onto each FPD doc (`aa_w26`). Weeks 27-34 do not update.
- Week 35: final = frozen week-26 score + postseason bonus (`compute_final`, via `_persist_week_35_awards_if_needed`).
- News stories after weeks 0 (preseason, shown as week 1), 7, 13, 19, 26: type `all_americans`, ids `w{n}-all-americans`.

Stored under `awards`:

| Key | Holds |
|---|---|
| `all_american_projection` | `{season, week, label, weights, all_american_teams, frozen, computed_at}` |
| `all_american_teams` | The FINAL only: `{first_team, second_team, third_team}`. Read by `trophy_log.py` and `career_data.py`. Each pick adds `position`, `rating`, `rank`, `score`, `components`, `bonus`. |
| `all_american_final` | `{season, basis, week26_clean, third_team_ranks}`. `basis` is `week_26`, or `season_to_date` for a franchise that never froze. |

#### Tunable Constants (`BackEnd/utils/all_american.py`)

| Constant | Value | Effect |
|---|---|---|
| `WEIGHT_ROWS` | week 1: 100/0/0, week 10: 30/70/0, week 26: 0/70/30 | Attributes / stats / team weights; straight line between rows. |
| `STAT_WEIGHTS` | PTS 35, REB 15, AST 15, STL 10, BLK 10, DEF% 15 | Share of the stats score. |
| `MIN_GAMES_SHARE` | 0.70 | Share of the team's games a player needs for a stats score. |
| `DEF_ATTEMPTS_PER_GAME` | 5 | Defensive attempts per team game for a DEF% (the old 130 over 26 games). |
| `NEWS_COMPLETED_WEEKS` | 0, 7, 13, 19, 26 | Weeks a story publishes. |
| `BONUS_CONFERENCE_CHAMPION` / `BONUS_REGION_CHAMPION` / `BONUS_NATIONAL_SEMIFINAL` / `BONUS_NATIONAL_CHAMPION` | 1 / 2 / 2 / 5 | Team bonus points, cumulative. National `round2` is the semifinal. |
| `INDIVIDUAL_BONUS_TIERS` | top 10% +5, 25% +3, 50% +1 | One tier, by tournament per-game stat score at the position. |
| `MIN_TOURNAMENT_GAMES` | 2 | Tournament games needed for the individual bonus. |

### FCC Week 35 State

- top-right CTA copy = `Recruiting`
- CTA click opens `recruiting-orders.html`
- below the CTA, show bold green copy `Recruiting Is Live`
- the old green recruiting-access button is not used for week `35`
- Resources -> Recruits still opens `recruiting.html`

### Week 35 Recruiting

- week `35` is the actual commitment / signing phase
- recruiting-orders page header copy = `Recruiting Focus List`
- week `35` boards use a 20-point recruiting budget
  - `Points Remaining` updates live as the user edits point inputs
- `Save Orders` saves the user board and generates CPU week-35 boards if those CPU boards are still empty
- CPU week-35 orders only generate once per team
- `Run Recruiting` behaves as save-first-then-run
- when `Run Recruiting` finishes:
  - recruiting assignments resolve
  - walk-ons are generated where needed
  - week advances from `35` to `36`
  - user is redirected to `recruiting.html`

## Week 36 Wrap-Up State

- recruiting is closed
- FCC top-right CTA copy = `Go To Next Season`
- CTA uses a confirmation modal
- Resources -> Recruits opens `recruiting.html`, now acting as the signed-results page
- roster pages still show graduating seniors during week `36`
  - append bold green `(GR)` next to their names

## Go To Next Season

When the user confirms `Go To Next Season`:

- current-season game docs for the franchise are deleted
- franchise standings/results are reset
  - `franchise.results` is cleared, so W / L / PF / PA all return to zero for the new season
- seniors are removed from the franchise instance
- signed recruits and walk-ons are carried into the next season
  - when they are materialized into next-season franchise player docs, their recruit attributes are normalized into the full franchise-player shape
  - this includes anchor baselines for core attributes plus initialized `CH`, `EM`, `MO`, and `NG`, so week 1 training camp treats them like normal franchise players
- career stats persist
- season stats reset
- each team's offensive play `season_stats.player_points` map is cleared
  - this resets the Playbooks / FCC per-play top-scorer tracking for the new season
  - play configuration and non-scorer play metadata remain intact
- a new franchise-season schedule is generated
- old FRD docs are deleted
- 300 new recruits are generated for the next season
- roster rendering for the next season is franchise-instance driven
  - signed recruits and walk-ons do not need universal `players` docs to appear on roster pages

For the detailed franchise-instance rollover process, see `Season_Init_System.md`.

### Senior Tribute

Pressing **Go To Next Season** plays a tribute to graduating seniors in place of the
season-transition load screen. Module: `FrontEnd/static/js/shared/seniorTribute.js`.
*(Merged from `projects/Senior_Tribute_Brief.md`, 2026-09-14.)*

| | |
|---|---|
| Sequence | snapshot tribute → start `finish-season` in the background → slideshow → resolution screen → **Advance To Next Season** (load cover only if rollover is still running) |
| Who | user team **active-roster** seniors/graduates only — training squad, practice squad and cuts are excluded |
| Order | RT descending |
| Hold | `HOLD_MS = 6000` per card. No skip, no pause |
| Hero | the player headshot, not the team logo — unlike the recruiting reveal, the team is already known |
| No seniors | tribute skipped; the normal season-transition load screen plays |
| Layer | full-screen takeover above the auth bar: `.st-host` z-index **10010** (bar is 9998). Below modals/toasts (10020+), maintenance banner, `PageLoadOverlay` |
| Advance while rollover still running | the season-transition cover (`.fcc-season-advance`, z 4000) is shown and the tribute is torn down — otherwise the cover would sit hidden behind it |

Design: **"Last Page"** (handoff: `projects/senior-tribute-handoff/`).

**Slide:** bottom-anchored editorial layout. Left — eyebrow `Class of Season N · #jersey · POS`,
given name (muted) over surname, hairline rule, career PPG / RPG / APG / DEF%,
`{games} games · {points} career points`, orange title marks. Right — the transparent portrait
bleeding off the bottom edge with the jersey number ghosted behind. A 2px bar across the top
fills over the hold. Slides overlap on change (outgoing fades/drifts left).

**Resolution:** `Class of Season N` + `N seniors · thank you`, a centred grid of portrait cards
(name, `POS · N games`, stat strip, one orange mark per title), then the green CTA. **Never
scrolls.** The last slide's portrait travels into its card.

**Payload per senior** (`BackEnd/utils/senior_tribute.py`): `player_id, name, first_name,
last_name, rt, ppg, rpg, apg, def_pct, titles, jersey_number` (`meta.jersey`), `position`
(best-rated key of `position_ratings`), `games_played` (`career.GP`), `career_points`
(`career.PTS`). No "seasons with the program" field exists, so the career line omits it.

**Fallbacks:** a failed portrait shows the jersey number (or initials) on the slide and initials
on the card — never a broken image. A missing jersey omits `#NN` and the ghost numeral.

**Green** appears only on the Advance button; titles are orange marks, never chips.
**Team primary colour** is atmosphere only — one soft radial on the host (`teamColor` from FCC).
**Reduced motion:** entrances are a 150ms fade, the bar steps per slide, no portrait FLIP. The
6s cadence is unchanged.

**Titles** are player-specific on `fpd.titles` (`conf_rs`, `conf_t`, `region`, `national`),
incremented on the user team's active roster when a title is awarded. Future-forward only — no
historical backfill. A title kind is hidden when its count is 0.

#### Tunable Constants — Senior Tribute

| Constant | Where | Value | Effect |
|---|---|---|---|
| `HOLD_MS` | `seniorTribute.js` | 6000 | Time per slide; the top bar fills over it |
| `SLIDE_OUT_MS` | `seniorTribute.js` | 320 | When the outgoing slide is removed (CSS fade/drift is 300ms) |
| `FLIP_MS` | `seniorTribute.js` | 520 | Last portrait's travel into its resolution card |
| `CARD_STAGGER_MS` | `seniorTribute.js` | 55 | Delay between resolution cards arriving |
| `CTA_AFTER_LAST_CARD_MS` | `seniorTribute.js` | 300 | CTA fade-in after the last card starts |
| `LONG_NAME_CHARS` | `seniorTribute.js` | 18 | Above this the slide name steps down a size |
| Class-size buckets | `senior-tribute.css` `.st-c-1/-few/-many` | 1 → 300px card · 2–6 → 188px, one column each · 7–12 → 6 columns × 154px | Card width + portrait height per class size |
| Breakpoint | `senior-tribute.css` | 820px | Slide stacks; resolution goes to 3 (2–6) / 4 (7–12) columns, stat labels drop |

### Coaching focus habit counters (FTD)

- Each franchise team’s FTD may store **`coaching_focus`** tallies (archetype usage during the season).
- When the user confirms **Go To Next Season** and `finish_season` runs, each team’s four counters are **not** wiped: they are set to **`round(prior × 0.25)`** (integer), i.e. **75% of the prior value is removed** and the remainder seeds the new season. See `Training_System.md` (Data Storage → FTD) and `BackEnd/utils/franchise_coaching_focus_counts.py` (`carryover_coaching_focus_counts_for_new_season`).
