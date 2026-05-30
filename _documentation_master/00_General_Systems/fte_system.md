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
| 4 | **Set Lineup** | `set-lineup.html?mode=tutorial&...` | `set_lineup` → `in_game` | Centered Functional modal w/ team Sammy (intro on load + feedback on CTA click) | `GOT IT` orange (intro); `RETURN TO GAME` green (gating; also relabeled on the page CTA) |

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

Green = gating (advances game state). Orange = non-gating primary. In the FTE flow, **two green buttons by design**: the Tip-off `SET LINEUP` and the set-lineup-page `RETURN TO GAME` (both advance game state). Username `CONTINUE`, Persona `LET'S GO`, lineup intro `GOT IT`, and any other onboarding CTA are orange. The lineup-feedback modal's `RETURN TO GAME` is the green CTA (it's the actual navigation trigger; the page-level Return To Game button just opens the feedback modal).

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
| `set_lineup` | tip-off CTA | `/set-lineup.html?mode=tutorial&quarter=4&...` (slots load empty) | `RETURN TO GAME` → opens lineup-feedback modal → modal CTA advances to `in_game` and navigates |
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
| `team.lineup` | engine-derived starting five (from `rank_roster`) — **harmless default**; the frontend no longer surfaces these as URL hints on set-lineup, and the user's chosen lineup overrides this on Return To Game |
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
| `js/shared/tutorialProgressThread.js` + `css/tutorial-progress.css` | 6-dot progress indicator |
| `js/shared/tutorialLineupModals.js` + `css/tutorial-lineup-modal.css` | Set-lineup intro + post-lineup feedback modals; also exports `pickLineupFeedbackMessage` (the algorithm) |
| `js/shared/attributeTour.js` + `css/attribute-tour.css` | First-run attribute-discovery tour on tutorial set-lineup (scrim + lifted header row + shimmer cues + Sammy coach-mark + X-of-N counter) |
| `js/shared/coachMark.js` + `css/coach-mark.css` | Spotlight tooltip primitive — **available but not currently used in the FTE flow** (set-lineup intro switched to a centered Functional modal); kept for future tutorials |
| `js/shared/getGameMode.js` | Single source of truth for the mode value passed to EOG popup (see §8) |
| `js/shared/rtBucket.js` + `css/rt-buckets.css` | RT color bucket helper (exposes `window.getRtBucketClass`) |
| `css/gob-buttons.css` | `.gob-btn` system (--action / --gate / --ghost / --lg) |
| `images/sammy_tutorial.png` | Generic Sammy (Screen 0 only) |
| `images/coaches/<abbr>/Sammy-<abbr>.png` | Team-linked Sammy (Screens 2–4 + EOG) |

### Canonical modal/pattern classes

| Pattern | Classes / file | Used by |
|---|---|---|
| Functional modal | `.gob-modal-*` in `resource-pages.css` (canonical = Auto-Train confirmation in `training.html`) | Username modal, set-lineup intro modal, set-lineup feedback modal |
| Moment modal | inline in `css/tutorial-tipoff.css` (canonical = `gameCompletionPopup.js`) | Tip-off, EOG |
| Coach-mark | `.gob-coachmark*` in `css/coach-mark.css` | Available primitive; not currently used in FTE |

### Set-lineup tutorial flow

The tutorial set-lineup intentionally loads with empty slots — the user fills their own lineup as part of the lesson. Three guided beats bracket the experience:

1. **Intro modal** (centered Functional-modal chrome with team-linked Sammy portrait overlapping the top, sessionStorage-guarded per `game_id`): "Here's your moment, Coach. Set your lineup for crunch time." Single `GOT IT` orange CTA.
2. **Attribute tour** (fires immediately after the intro dismisses, `localStorage`-guarded by `fteV2AttrTourSeen`): the user's first-run nudge that reveals the per-attribute hover tooltips that already live on the column headers. See "Attribute tour mechanic" below.
3. **Feedback modal** (fires every Return To Game click; same chrome as intro): algorithm-chosen message + single green `RETURN TO GAME` CTA that performs the actual navigation to `court.html`.

The page-level `play-now` button is relabeled "Return To Game" in tutorial mode (still uses the existing green disabled-until-complete styling).

### Attribute tour mechanic

Module: [`js/shared/attributeTour.js`](FrontEnd/static/js/shared/attributeTour.js) + [`css/attribute-tour.css`](FrontEnd/static/css/attribute-tour.css). Tutorial mode only. Fires once per browser (localStorage flag `fteV2AttrTourSeen`).

**Stacking approach.** We DIM the surrounding siblings directly instead of laying a full-screen scrim on top. Reason: `<thead>` z-index is unreliable against a full-screen overlay — an earlier build had the lifted header row + its gold ring rendering UNDER the scrim. Dimming siblings keeps the header at its natural position, fully lit, with the ring always visible.

| Layer | What |
|---|---|
| Dimmed siblings | Caller passes a `dimSelectors` array (banner, score bar, ATTRIBUTES/STATS toggle, tbody, footnote, right-hand Starting Five panel, action buttons). Each matched element gets `.attribute-tour-dim` → `opacity: 0.30; pointer-events: none`. |
| Lifted header row | No z-index lift — nothing covers it. Gold ring + soft glow (`box-shadow: 0 0 0 1px rgba(247,148,32,0.5), 0 0 38px rgba(247,148,32,0.18)`) applied per `<th>`, with internal edges merging into a single horizontal band. |
| Shimmer cue | Each header that maps to a known attribute (per `attributeTooltips.js`) gets a slow ~2.4s gold underline pulse — invitation to hover, not a demand. |
| Hover/explored states | Hover → orange tint. Once hovered → green tint + shimmer suppressed; counter increments. |
| Sammy coach-mark | Compact fixed-position bubble below the header row with team-linked Sammy, eyebrow `QUICK TOUR`, body copy, live `X of N explored` counter, ghost `GOT IT` dismiss. Button stays at 55% opacity until all headers are explored, then full opacity. Always clickable. |
| Touch fallback | On `touchstart` of a header: synthesize `mouseenter` (so the existing tooltip helper fires) + mark explored. Auto-dispatches `mouseleave` 3s later so taps elsewhere don't leave a stuck tooltip. Scoped to the tour — `attributeTooltips.js` is unchanged. |

**N** = headers whose text content strictly matches a known attribute key (SC SH ID OD PS BH RB ST AG ND IQ FT + HT WT NG). The Player Name th's inline `RT` label is intentionally excluded since RT lives inside the name column, not as its own header.

**Dismissal**: `GOT IT` lifts the dim, fades Sammy, restores every class the tour added, sets the localStorage flag. After dismissal the tooltips behave exactly as before — the tour is one-shot UI; the underlying tooltip helper is permanent.

### Set-lineup feedback algorithm

Implemented in `js/shared/tutorialLineupModals.js → pickLineupFeedbackMessage(starters, fullRoster)`. Source of truth lives in the module; this section mirrors it.

**Pool composition** (all checks run together; build a candidate pool, then pick):

| Check | Qualifies if | Message |
|---|---|---|
| **Talent** | The 5 chosen starters are the team's top-5 by highest RT (ties at the 5th-place RT all count as eligible) | "You're putting your five best players on the court. Smart." |
| SC & SH | Both in top-2 attrs | "You're leading with your best scorers, good luck, Coach." |
| ID & OD | Both in top-2 | "You're leading with your best defenders, good luck, Coach." |
| (SC or SH) and (ID or OD) | One of each in top-2 | "You're balancing offense and defense, good luck, Coach." |
| RB & ST | Both in top-2 | "You're leading with your strong rebounders. Let's see how well they clean the boards." |
| (ID or OD) and ST | At least one defensive + ST in top-2 | "You're leading with muscle and defense. You're an intimidator, Coach." |
| (SC or SH) and AG | Offensive + AG in top-2 | "You're leading with your athletic scorers. I like it, Coach." |
| PS & BH | Both in top-2 | "You're leading with fundamentals. I like the discipline, Coach." |
| ND & AG | Both in top-2 | "This lineup is fast and athletic. Our opponent will have a difficult time keeping up with us." |
| (SC or SH) and IQ | Offensive + IQ in top-2 | "This is a smart offensive lineup." |
| (ID or OD) and IQ | Defensive + IQ in top-2 | "This is a smart defensive lineup." |
| 2+ of (ST, AG, ND) | At least two of those three in top-2 | "Leading with pure athleticism. I like it, Coach." |
| (PS or BH) and IQ | Either + IQ in top-2 | "A very cerebral and disciplined lineup. Good luck, Coach." |
| (SC or SH) and (ST/AG/ND) | Offensive + any athleticism in top-2 | "This is an athletically focused offensive lineup. Good luck, Coach." |
| (ID or OD) and (ST/AG/ND) | Defensive + any athleticism in top-2 | "This is an athletically focused defensive lineup. Good luck, Coach." |
| (SC or SH) and (BH or PS) | Offensive + fundamentals in top-2 | "This is a technically focused offensive lineup. Good luck, Coach." |
| (ID or OD) and (BH or PS) | Defensive + fundamentals in top-2 | "This is a technically focused defensive lineup. Good luck, Coach." |
| (SC or SH) and RB | Offensive + RB in top-2 | "This is a rebounding focused offensive lineup. Good luck, Coach." |
| (ID or OD) and RB | Defensive + RB in top-2 | "This is a rebounding focused defensive lineup. Good luck, Coach." |

**Top-2 attrs** = the set of attribute IDs whose total across the 5 starters is at the #1 or #2 rank (ties at either rank all included). Attrs in play: `SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ`.

**Pick rule**: pool size 1 → use it. Pool size 2+ → random pick. Pool size 0 → Unconventional: "A very unconventional lineup, Coach. You're going to keep our opponent very off-balance."

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
| 5 | **Forgetting to flush `sessionStorage` lineup-intro guard on rerun.** Tutorial set-lineup intro modal uses key `fteV2TutorialLineupModalShown_${gameId}` (renamed from the prior coach-mark / Sammy-modal keys; old keys are harmless leftovers). Each fresh game_id gets its own key so re-tours work. | No action needed; documented so you don't think it's broken when it skips on re-entry. |

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
##If User has the players with the top 5 RT values on the team, add Talent message to the list of possible choices.

##Skill based logic
- Attributes in play: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ
- Step 1: Calculate the total attributes value for attributes in play for the user's lineup. 
- Step 2: Identify the top 2 attributes in terms of total. If 2 or more are tied for the second, include them all. Example: 1. SC: 54, 2. SH: 53, ST: 53, IQ: 53 -- all four of those would be considered "Top 2". LMK if that is not clear.
- Step 3: Choose the outgoing modal messsage based on the top 2 attributes.

##Outgoing modal messages
**Talent** 
- "You're putting your five best players on the court. Smart." (Talent-Led)
**Skill Based** Track all of the below that qualify based on the top 2 attributes for the lineup
- SC & SH: "You're leading with your best scorers, good luck Coach." (Offense-Led)
- ID & OD: "You're leading with your best defenders, good luck Coach." (Defense-Led)
- one of (SC or SH) and one of (ID or OD): "You're balancing offense and defense, good luck Coach." (Balanced)
- RB & ST: "You're leading with your strong rebounders. Let's see how well they clean the boards." (Straight Intimidation)
- one of (ID or OD) and ST: "You're leading with muscle and defense. You're an intimidator, Coach."(Defensive Intimidation)
- one of (SH or SC) and AG: "You're leading with your athletic scorers. I like it Coach." (Offensive Quickness)
- PS & BH: "You're leading wtih fundamentals. I like the discipline, Coach." (Fundamentals)
- ND & AG: "This lineup is fast and athletic. Our opponent will have a difficult time keeping up with us." (Speed)
- one of (SC or SH) and IQ: "This is a smart offensive lineup." (Intelligent Offense)
- one of (ID or OD) and IQ: "This is a smart defensive lineup." (Intelligent Defense)
- two of (ST, AG, ND): "Leading with pure athletcisim. I like it, Coach." (Pure Athleticism)
- one of (PS or BH) and IQ: "A very cerebral and disciplines lineup. Good luck Coach." (Cerebral Discipline)
- one of (SC or SH) and one of (ST, AG, ND): "This is an athletically focused offensive lineup. Good luck Coach." (Offensive Athleticism)
- one of (ID or OD) and one of (ST, AG, ND): "This is an athletically focused defensive lineup. Good luck Coach." (Defensive Athleticism)
- one of (SC or SH) and one of (BH or PS): "This is an technically focused offensive lineup. Good luck Coach." (Technical Offense)
- one of (ID or OD) and one of (BH or PS): "This is an technically focused defensive lineup. Good luck Coach." (Technical Defense)
- one of (SC or SH) and RB: "This is an rebouning focused offensive lineup. Good luck Coach." (Offense & Rebounding)
- one of (ID or OD) and RB: "This is an rebounding focused defensive lineup. Good luck Coach." (Defense & Rebounding)

**Unconventional Message**
- "A very unconventional lineup, Coach. You're going to keep our opponent very off-balance." (Unconventional)
