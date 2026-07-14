# Pre-Game Experience System

> **Last Updated:** July 2026  
> **Purpose:** Franchise-mode Q1 cinematic (starting-five reveal → defense matchups → tip-off) that replaces the Q1 defense-matchups popup. Mid-game matchups keep the Strategic Modal footprint with the same card DNA.

**Related:** [Defense Matchups System](./Defense_Matchups_System.md)  
**Mocks (source of truth):**  
- `_documentation_master/projects/UESS Audits/Pre-Game Experience.html`  
- `_documentation_master/projects/Defense Matchups - In-Game Modal.html`

---

## Scope

| Mode | Q1 (Play Quarter) | Later breaks / timeouts / foul-outs |
|------|-------------------|-------------------------------------|
| **Franchise** | Full-screen pre-game experience | Restyled in-game defense matchups modal |
| **Single game** | Restyled in-game modal (no cinematic, no pregame bed) | Same modal |
| **Tutorial** | Skipped entirely | Skipped entirely |

Sim Quarter / Sim Full Game never open matchups UI (unchanged gate: `shouldShowMatchupsPopup && animate`).

---

## Flow (Franchise Q1)

1. Set Lineup → `court.html` → Gameplay Buttons → **Play Quarter**
2. `gameScene` awaits `showDefenseMatchupsPopup(gameId, scene, { isQ1Start: true })`
3. Franchise Q1 → `showPreGameExperience(...)` (full-screen overlay)
4. Phases:
   - **Reveal** — “Tale of the Tape”; rows land PG→C (~820ms apart) with `click-beep`
   - **Matchups** — drag user defenders; CTA becomes **Submit & Tip Off**
   - **Tip Off** — veil ~1.9s, then dissolve; pregame bed stops; promise resolves → tip-off / Q1 animation
5. Later Play Quarter entries use the **in-game modal** only (same cards, game stats, Strategic Modal box)

---

## Layout & Matchup Model

- **Columns:** home **left**, away **right** (all surfaces: reveal, pre-game matchups, in-game modal)
- **Draggable column:** only the **user** side (left if user is home, right if user is away)
- **Assignment:** defender in slot *i* guards opponent position `POSITIONS[i]` (`PG`…`C`)
- **Save shape (unchanged):** `{ userPos: guardedOppPos }` via `POST /api/save-man-defense-matchups`

**Reveal (lineup announce):** title `AWAY @ HOME`; records strip `#Rank W-L` away then home (FTD `natl_rank` + standings W-L); RT in fixed outer gutter (same as matchups — no headshot badge); center position label colored to favorability; season stats; no eyebrow / no rolling subline.

**Matchups (pre-game step + in-game modal):** RT in the same fixed outer gutter (Attribute Bar Scale color, tabular-nums, 3-digit-safe); arrows only in center; **game** PTS/REB/AST/DEF%; drag keeps each player's own-position RT.

**RT gutter:** Home rows are `[RT][info+headshot]` (RT left-aligned); away rows are `[info+headshot][RT]` (RT right-aligned). Gutter width is fixed so every row’s RT shares the same x.
Favorability: RT diff ≥ 3 → bold 4px border + arrow toward the stronger player in that team’s primary; within 2 → both white 2px borders + neutral silver double arrow.

---

## Data

**Endpoint (expanded, no new routes):** `GET /api/game/{game_id}/lineup-for-matchups`

Returns:

- `home_team` / `away_team` (name, colors, players)
- `user_team` / `computer_team` (legacy aliases)
- `user_team_side`, `current_matchups`
- `franchise_id`, `franchise_week`, `is_franchise`, `is_tournament_context` (week ≥ 27)
- Per player: `player_id`, `position`, `name`, `jersey`, `height`, `weight`, `rt` (position RT), `game_stats` (PTS/REB/AST/DEF%), `season_stats` (PPG/RPG/APG/DEF%/GP), plus legacy `attributes` / `stats` keys

| Surface | Stat strip | RT treatment |
|---------|------------|--------------|
| Pre-game **reveal** | **Season** PPG/RPG/APG/DEF% (FPD) | Fixed outer gutter (tall number) |
| Pre-game **matchups** + in-game modal | **This game** PTS/REB/AST/DEF% | Fixed outer gutter (tall number) |

Team blocks also include `natl_rank`, `wins`, `losses` for the reveal records strip.

Images: `API_CONFIG.getPlayerImageUrl(player_id, { size: 'card' })`, lazy, 176×176, silhouette fallback.

RT badge background uses Attribute Bar Scale (≤40 red, 41–60 yellow, 61–80 green, 81+ blue).

---

## Suppression Flags (independent)

| Key | Behavior |
|-----|----------|
| `pregameSkipIntro_<gameId>` | Skip Intro jumps to matchups; persists for this game so resume doesn’t replay the reveal |
| `defenseMatchupsDontShow_<gameId>` | Suppresses **all** matchups UI for the rest of the game (Q1 + mid-game), same as before |

`resetDontShowAgainFlag(gameId)` on a truly new game clears both of the above plus the announce-played key.

---

## Audio

| Asset | When |
|-------|------|
| `pregame-regular-season.mp3` | Franchise Q1 pre-game bed (regular season) |
| `pregame-conf-tourney.mp3` | Franchise Q1 pre-game bed when `is_tournament_context` (week ≥ 27 / EOS tournaments) |
| `click-beep.wav` | Each reveal row land (×5) |
| `defense-sammy.mp3` | In-game modal open only (first time per game); **not** during pre-game |

Bed starts with the cinematic and **stops** when the Tip Off veil dissolves. It must not play during mid-game modals.

Sounds live under `FrontEnd/static/sounds/` (gitignored; track via Git LFS when adding new files).

---

## Frontend Files

- `FrontEnd/static/js/phaser/utils/defenseMatchupsPopup.js` — entry, franchise Q1 gate, in-game modal
- `FrontEnd/static/js/phaser/utils/preGameExperience.js` — cinematic phases
- `FrontEnd/static/js/phaser/utils/matchupsUiShared.js` — tiles, order↔matchups, save helper
- `FrontEnd/static/js/phaser/utils/gameSfx.js` — `startPregameBed` / `stopPregameBed` / `playPregameRevealClick`
- `FrontEnd/static/js/phaser/gameScene.js` — passes `{ isQ1Start }` into the popup await

---

## Acceptance Criteria

- Franchise Q1 Play Quarter shows cinematic, not the old attribute-strip popup
- Home left / away right; only user column drags; save still maps user pos → guarded opp pos
- Pre-game season stats from FPD; in-game modal uses live game stats
- Skip Intro and Don’t Show Again use the sessionStorage keys above
- Pregame bed + click-beep on franchise Q1 only; bed stops at tip-off
- Tutorial skips; single-game never gets the cinematic
- Mid-game modal matches Defense Matchups in-game mock footprint (~1000px Strategic Modal)
