# FTE System (Source of Truth)

> **Purpose.** Single reference for the live First-Time Experience funnel. Future threads working on FTE without this thread's memory should read this first; it consolidates and supersedes the four files this replaced.
>
> **Supersedes:** `projects/fte_overview.md`, `projects/fte_tutorial_game_spec.md`, `projects/fte_implementation_plan.md`, `projects/fte_inject_state.md`.

---

## 1. At a glance

A brand-new user gets a 5-screen funnel — Persona Intro → Pick Program → Username → Pre-Game Tip-off → Set Lineup — then plays a real 4-minute Q4 game vs a nerfed opponent. On the locker-room click, their debut publishes to the mode-select Live Feed and their FTE marker flips to complete. The tutorial game touches **no** franchise or tournament state.

```
signup ──▶ persona_intro ──▶ team_select ──▶ username ──▶ situation ──▶ set_lineup ──▶ in_game ──▶ complete
                                                                                                    │
                                                                                              debut published
                                                                                              + mode-select
```

Grandfathered users (those who already had a franchise when FTE v2 shipped, or new users post-tutorial) have `fte_v2_complete: true` and bypass the funnel entirely.

---

## 2. The five screens

| # | Screen | Page / surface | Step ID | Canonical pattern | Primary CTA |
|---|---|---|---|---|---|
| 0 | **Persona Intro** | `tutorial-persona-intro.html` | `persona_intro` | Full-screen, on-system shell | `LET'S GO` orange |
| 1 | **Pick Your Program** | `franchise-select-team.html?mode=tutorial` | `team_select` | Existing team cards + orange-ring selected state | (card tap opens modal) |
| 2 | **Username** | Functional modal over screen 1 | `username` | `.gob-modal-*` chrome (Functional) | `CONTINUE` orange |
| 3 | **Pre-Game Tip-off** | `tutorial-situation.html` | `situation` | Moment modal (560px, banner bg, score hero) | **`SET LINEUP` green** ← only green in the flow |
| 4 | **Set Lineup** | `set-lineup.html?mode=tutorial&...` | `set_lineup` → `in_game` | Coach-mark (not a modal) anchored to roster | `GOT IT` ghost (acks tip); `PLAY GAME` green (gating, outside FTE scope) |

The actual game runs on `court.html?mode=tutorial`; the End-of-Game modal renders the tutorial variant of `gameCompletionPopup.js`.

### Sammy variants

| Screen | Variant | Asset |
|---|---|---|
| 0 — Persona Intro | Generic (white kit) | `/images/sammy_tutorial.png` |
| 2–4 + EOG | Team-linked (team kit) | `/images/coaches/<abbr>/Sammy-<abbr>.png` |

Helper: `FrontEnd/static/js/shared/teamCoachAsset.js`. Team-name → abbreviation map:

| Team | Abbr |
|---|---|
| Bentley-Truman | BT |
| Four Corners | FC |
| Lancaster | Lan |
| Little York | LY |
| Morristown | Mor |
| Ocean City | OC |
| South Lancaster | SL |
| Xavien | Xav |

### Action color (Styleguide §)

Green = gating (advances game state). Orange = non-gating primary. In the FTE flow, **exactly one green button**: the Tip-off `SET LINEUP`. Username `CONTINUE`, Persona `LET'S GO`, and any other onboarding CTA are orange. Coach-mark `GOT IT` is ghost — it's an acknowledgement, not an action.

Universal button class system: `FrontEnd/static/css/gob-buttons.css` (`.gob-btn--action` / `--gate` / `--ghost`, plus `--lg`).

### Progress thread

Quiet 6-dot indicator at the bottom of every funnel screen. Module: `FrontEnd/static/js/shared/tutorialProgressThread.js`; CSS: `FrontEnd/static/css/tutorial-progress.css`. Step IDs: `persona | program | username | tipoff | lineup | gameplay`. Hidden on `court.html` — `gameplay` is therefore never the active step; it always renders as a faint pending dot, signaling the final stop.

---

## 3. State machine

`users.tutorial_state.step` is the source of truth. Server enforces forward-only transitions via `POST /api/auth/tutorial-advance`.

### Enum (`auth_routes.py`)

```python
TutorialStep = Literal[
  "persona_intro",  # 0  ← screen 0
  "team_select",    # 1  ← screen 1 (entry)
  "username",       # 2  ← screen 1 (after card tap, modal open)
  "situation",      # 3  ← screen 3
  "set_lineup",     # 4  ← screen 4
  "in_game",        # 5  ← court.html
  "complete",       # 6  ← debut published, fte_v2_complete=True
]
```

### Step → page → endpoint (the canonical handoff)

| Step | Set by | Destination page | Endpoint that advances |
|---|---|---|---|
| `persona_intro` | signup default | `/tutorial-persona-intro.html` | `LET'S GO` → advance to `team_select` |
| `team_select` | persona-intro CTA | `/franchise-select-team.html?mode=tutorial` | card `Select` → advance to `username` (+ `team_pick`) |
| `username` | card select | (modal stays on team-select) | `CONTINUE` → set-username + advance to `situation` |
| `situation` | username success | `/tutorial-situation.html` | `SET LINEUP` → init-game + advance to `set_lineup` |
| `set_lineup` | tip-off CTA | `/set-lineup.html?mode=tutorial&quarter=4&...` | `PLAY GAME` → advance to `in_game` |
| `in_game` | play CTA | `/court.html?mode=tutorial&...` | game completes → `complete` |
| `complete` | EOG locker-room click | `/mode-select.html` | (terminal; `fte_v2_complete=true`) |

### User-document shape

```python
{
  "fte": True,             # legacy flag, preserved
  "fte_v2_complete": False,
  "tutorial_state": {
    "step": "persona_intro",
    "team_pick": None,
    "started_at": <ISO>,
    "completed_at": None,
  }
}
```

---

## 4. Routing (frontend)

### `routeToTutorial(meData)` in `js/shared/authBarInit.js`

Fires from `initAuthState()` after `/api/auth/me` returns. If `fte_v2_complete === false`, maps `tutorial_state.step` → destination and `window.location.replace()`s. The handler runs on auth-bar-bearing pages only; `PAGES_WITHOUT_AUTH_BAR` pages don't trigger routing.

### Auth-bar suppression

- Persona Intro, Situation, Set-Lineup, Court, Game-Plan, Playbooks, etc. are in `PAGES_WITHOUT_AUTH_BAR`.
- Any page loaded with `?mode=tutorial` ALSO suppresses the auth bar (`shouldShowAuthBar()` check).

### Shoulder pages

Pages reachable from the funnel but not themselves a step. When `?mode=tutorial` is present in their URL, `routeToTutorial` returns early so the user isn't bounced back to their current step. Today: `/team-roster-view.html` (entered via Scout from Pick Program).

---

## 5. Backend

### Endpoints

| Method | Path | Role |
|---|---|---|
| `POST` | `/api/auth/signup` | Create user with `fte_v2_complete: false`, `tutorial_state.step = "persona_intro"` |
| `GET` | `/api/auth/me` | Returns `fte_v2_complete` + full `tutorial_state` |
| `POST` | `/api/auth/set-username` | Persists username; unchanged from FTE v1 |
| `POST` | `/api/auth/tutorial-advance` | Body `{ step, team_pick? }`. Forward-only |
| `POST` | `/api/auth/tutorial-complete` | Sets `fte_v2_complete=true`, `tutorial_state.step="complete"`, `completed_at=now`. Called from EOG locker-room handler |
| `POST` | `/api/init-game` | When `mode == "tutorial"`, calls `apply_tutorial_initial_state` (see §6) |
| `POST` | `/api/community/debut` | Best-effort debut publish to mode-select Live Feed |

### Tutorial game module: `BackEnd/utils/tutorial_game.py`

Central orchestrator. Key constants:

| Name | Value | Notes |
|---|---|---|
| `USER_SHOT_THRESHOLD` | `10` | User team forced-make threshold |
| `COMPUTER_SHOT_THRESHOLD` | `110` | Opponent nerf (was 210; lowered 2026-05-29 — winnable but AI puts shots up) |
| `TUTORIAL_STRATEGY_SETTINGS` | `{offense:2, inside:2, attack:2, outside:2, aggression:2, fast_breaks:2, defense:2, rebounding:2, hc_trap:1, fc_press:1, tempo:2}` | All keys default 2; HCT + FCP = 1 |
| `TUTORIAL_FAST_BREAKS_PCT` | distribution map | Per-key % for `fast_breaks` setting |
| `TUTORIAL_ZONE_DEFENSE_PCT` / `TUTORIAL_MAN_DEFENSE_PCT` | distribution maps | Defensive playcall mix |
| `TUTORIAL_USER_OFFENSE_PLAYCALLS` | 8 plays | `3-2 Motion`, `4-1 Motion`, `5-0 Motion`, `PF Post Motion`, `Base Post Play`, `Pick & Roll - Entry Pass`, `Iso`, `Double Screen Three - Wing` |

### Stat templates: `BackEnd/data/tutorial_rosters.py`

Two universal stat blocks (`USER_TEAM_STAT_TEMPLATE`, `COMPUTER_TEAM_STAT_TEMPLATE`) keyed by row (`Starting PG/SG/SF/PF/C`, `Backup 1..7`). `rank_roster()` derives the starting five for any team from `position_ratings`; backups stack-rank by best-position rating. `stat_overlay_for(position, side)` returns the appropriate stat dict.

Import-time invariants verify the templates sum-check (PTS totals match Section 4 quarter splits below).

### `apply_tutorial_initial_state(gm, summary, user_team_side)`

Mutates both `GameManager` and the `summary` dict. Injected state:

| Domain | Value |
|---|---|
| `quarter` | `4` |
| `clock` / `time_remaining` | `"4:00"` / `240` |
| `shot_clock_remaining` | `30` |
| `score` | tied `60–60` |
| `offensive_state` | `HCO` (with first turn as SIP via existing timeout-resume path) |
| `team_fouls` (Q4) | `3` / `3` |
| `timeouts` remaining | `1` / `1` |
| `home_crowd_factor` | `4` (user is always home) |
| `points_by_quarter` | user `[14, 18, 28, 0]` · opp `[18, 15, 27, 0]` |
| `player.stats["game"]` | per template (Section 5 data) |
| `player.metadata["fouls"]` | per template `F` column (cumulative; doesn't reset per Q) |
| `NG` (energy) all players | `0.95` |
| `MO` (momentum) all players | `0` |
| `team.lineup` | engine-derived starting five (from `rank_roster`) |
| `playbook_settings` | the 8 user offense plays above |
| `timeout_next_play_type` | `SIDE_INBOUND` |
| `game_stats_initialized` | `True` (critical — engine zeroes stats otherwise) |
| `shot_threshold` overrides | user `10`, opponent `110` |

### Opponent derivation

Default opponent is `Xavien`. If the user picks Xavien, fall back to `South Lancaster`. Logic in `tutorial-situation.js` (`deriveOpponent`).

### Game lifecycle

Tutorial follows the `single` path through `finalizeGame.js` (no franchise/tournament writes). The game doc is deleted on locker-room click via the existing `/api/games/delete-completed-single` precedent. Game-plan and playbook endpoints alias `mode=tutorial → single` in `BackEnd/api/gameplan_routes.py`.

---

## 6. Frontend file map

### Funnel screens

| File | Purpose |
|---|---|
| `tutorial-persona-intro.html` + `.js` + `css/tutorial-persona-intro.css` | Screen 0 |
| `franchise-select-team.html` + `.js` + `.css` | Screen 1 (also serves the franchise-creation path) |
| `js/shared/usernameModal.js` + `css/username-modal.css` | Screen 2 (Functional modal with portrait overlap) |
| `tutorial-situation.html` + `.js` + `css/tutorial-tipoff.css` | Screen 3 (Moment modal) |
| `set-lineup.html` + `.js` + `.css` | Screen 4 |
| `court.html` (+ Phaser stack) | Gameplay |

### Shared primitives

| File | Purpose |
|---|---|
| `js/shared/teamCoachAsset.js` | Team → Sammy image path |
| `js/shared/tutorialProgressThread.js` + `css/tutorial-progress.css` | 5-dot progress indicator |
| `js/shared/coachMark.js` + `css/coach-mark.css` | Spotlight tooltip primitive (Screen 4) |
| `js/shared/getGameMode.js` | Single source of truth for the mode value passed to EOG popup (see §8) |
| `js/shared/rtBucket.js` + `css/rt-buckets.css` | RT color bucket helper (exposes `window.getRtBucketClass`) |
| `css/gob-buttons.css` | `.gob-btn` system (--action / --gate / --ghost / --lg) |
| `images/sammy_tutorial.png` | Generic Sammy (Screen 0 only) |
| `images/coaches/<abbr>/Sammy-<abbr>.png` | Team-linked Sammy (Screens 2–4 + EOG) |

### Canonical modal/pattern classes

| Pattern | Classes / file | Used by |
|---|---|---|
| Functional modal | `.gob-modal-*` in `resource-pages.css` (canonical = Auto-Train confirmation in `training.html`) | Username modal |
| Moment modal | inline in `css/tutorial-tipoff.css` (canonical = `gameCompletionPopup.js`) | Tip-off, EOG |
| Coach-mark | `.gob-coachmark*` in `css/coach-mark.css` (new primitive — distinct from the three modal types) | Set-lineup intro |

### EOG / debut publish

`js/phaser/utils/gameCompletionPopup.js` — `isTutorial = mode === 'tutorial'` branch:
- Eyebrow `Your Debut` + win/loss flavor message above the score
- **No Box Score button** (tutorial game is throwaway)
- `Go To Locker Room` → `POST /api/community/debut` → `POST /api/auth/tutorial-complete` → `POST /api/games/delete-completed-single` → navigate `/mode-select.html`

All three POSTs are best-effort; any failure logs but doesn't strand the user.

### Debut entry render (mode-select)

`mode-select.js` debut-entry branch. Visual: standard Live Feed row + gold metallic border. Non-clickable (no franchise to click into).

---

## 7. Live Feed debut entry schema

`community_highlights_collection`:

```python
{
  "at": <ISO>,
  "entry_type": "debut",
  "variant": "debut",
  "username": str,
  "user_team_name": str,
  "opponent_name": str,
  "user_won": bool,
  "user_score": int,
  "opponent_score": int,
  "primary_color": str,
  "secondary_color": str,
}
```

Endpoint: `POST /api/community/debut` (`BackEnd/api/community_highlights_routes.py`). Helper: `_build_debut_entry`, `push_debut_entry` in `BackEnd/utils/community_highlights.py`.

---

## 8. Don't reintroduce

These are real regressions we've hit. Listed so the next person doesn't pay the same tax.

| # | Antipattern | Why it matters |
|---|---|---|
| 1 | **Local `function getRtBucketClass()` in a classic-script page.** Top-level function declarations in non-module scripts silently clobber `window.<sameName>`. A wrapper that delegates to `window.getRtBucketClass(rt)` becomes infinite recursion. | PR #537 → blank set-lineup in tutorial. Use a different local name (`rtBucketClassOrEmpty`) — see `set-lineup.js` for the canonical comment. |
| 2 | **Duplicated mode derivation at EOG callsites.** Four call-sites of `showGameCompletionPopup` were independently building `mode`. One missed the tutorial branch → Box Score reappeared, locker-room routed wrong, `tutorial-complete` never fired, authBar bounced back to situation. | Always go through `js/shared/getGameMode.js`. |
| 3 | **Stale `.pre-game-container` flash on court.html.** It used to default to visible; bootGame then decided whether to hide. Caused a "Play Quarter / Sim Quarter" flash before live court paint. | `.pre-game-container.hidden` by default. bootGame removes `.hidden` only when it explicitly wants to show. Overlay dismisses on `court-ready` event dispatched from `bootGame.initGame()`. Don't revert. |
| 4 | **Bare `.rt-low` etc. without `!important`.** Page-local `.roster-table td { color: ... }` rules (specificity 0,1,1) silently override the bucket classes (0,1,0). | `/css/rt-buckets.css` uses `!important` deliberately. These are canonical scale colors; they should always win. |
| 5 | **Forgetting to flush `sessionStorage` lineup-intro guard on rerun.** Tutorial coach-mark uses key `fteV2TutorialLineupCoachMarkShown_${gameId}`. Renamed from the prior Sammy-modal key; if you re-tour an existing user, prior runs' keys are harmless but new runs key off the fresh game_id. | No action needed; documented so you don't think it's broken when it skips on re-entry. |

---

## 9. Tutorial isolation guarantees (verified)

The tutorial game touches NO franchise/tournament state. Specifically:

- No `franchises_collection` writes (no `franchise_id` on game doc)
- No `tournaments_collection` writes (no `tournament_id`)
- `init-game` `mode=tutorial` branch uses `apply_tutorial_initial_state` and follows the `single` finalize path
- `game-plan` / `playbooks` endpoints alias `mode=tutorial → single` (no franchise lookup)
- Game doc deleted on locker-room click — no orphaned game state

A tutorial run is recoverable: if interrupted, server `tutorial_state.step` tells `routeToTutorial` where to put the user back. Forward-only enforcement prevents double-advance from a two-tab race.

---

## 10. History summary (PR trail)

For commit-level history, `git log --grep "FTE v2"`. High-level milestones:

| Date | Milestone |
|---|---|
| 2026-05-27 | Backend foundations: schema, migration, tutorial_rosters, init-game extension, debut publish, set-username + tutorial-advance + tutorial-complete endpoints. Migrated staging (13 users) + production (51 users, 41 grandfathered). |
| 2026-05-27 → 28 | Frontend cutover: tutorial-situation, set-lineup tutorial branch, EOG tutorial variant, debut Live Feed render. |
| 2026-05-28 → 29 | Staging-walk fixes: mascot fetch from `/teams`, tooltips on team pages, game-plan read-only, court-flash + getGameMode helper, Scout in tutorial. |
| 2026-05-29 | Onboarding redesign: Persona Intro page (`persona_intro` step prepended), modal taxonomy (Functional / Moment / coach-mark), green-scarcity rule, RT colors, `.gob-btn` system, progress thread, team Sammy assets, `COMPUTER_SHOT_THRESHOLD 210 → 110`. |
| 2026-05-29 | Polish: signup routes directly to current step (no mode-select flash); overlay before username→situation nav; RT colors extended to FCC + Recruiting + Recruiting Orders; coach-mark text alignment fix. |

---

## 11. Where to read what

| If you need… | Read |
|---|---|
| Step transitions / routing | `js/shared/authBarInit.js` → `routeToTutorial` |
| Backend init injection | `BackEnd/utils/tutorial_game.py` → `apply_tutorial_initial_state` |
| Stat templates | `BackEnd/data/tutorial_rosters.py` |
| EOG tutorial behavior | `js/phaser/utils/gameCompletionPopup.js` → `isTutorial` branch |
| Canonical button / modal / coach-mark CSS | `css/gob-buttons.css`, `resource-pages.css` (`gob-modal-*`), `css/coach-mark.css`, `css/tutorial-tipoff.css`, `css/username-modal.css` |
| Action color rules / Attribute Bar Scale | `_documentation_master/00_General_Systems/Styleguide_updated.md` |
| Visual reference / design notes | `_documentation_master/07_Design_Systems/FTE Onboarding Redesign.html` |


**Set Lineup Alogrithm**

