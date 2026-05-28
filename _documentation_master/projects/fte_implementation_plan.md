# FTE Tutorial Game — Implementation Plan

**Companion docs:**
- [fte_tutorial_game_spec.md](fte_tutorial_game_spec.md) — product spec
- [fte_inject_state.md](fte_inject_state.md) — game-engine state values
- [fte_overview.md](fte_overview.md) — current FTE behavior

**Design lens:** Simple, Stable, Scalable. Minimum new surface area. No invasive changes to franchise / single / tournament code paths.

---

## 1. Architecture at a glance

```
signup → mode-select (authBarInit.js entry decision)
           │
           ├─ fte_v2_complete === true → existing app (unchanged)
           └─ fte_v2_complete !== true → tutorial funnel
                 │
                 ├─ team_select   (franchise-select-team.html?mode=tutorial)
                 ├─ username      (modal, extracted from authBarInit)
                 ├─ situation     (new page: tutorial-situation.html)
                 ├─ set_lineup    (set-lineup.html?mode=tutorial)
                 ├─ in_game       (court.html?mode=tutorial)
                 ├─ payoff        (tutorial post-game modal — override of gameCompletionPopup)
                 ├─ publish       (POST debut entry to community_highlights)
                 └─ land          (mode-select, debut visible in Live Feed)
```

State machine lives server-side as `users.tutorial_state.step`. Each frontend step bumps the server before navigating. Server only allows forward advancement.

---

## 2. Schema changes

### 2.1 User document (`users` collection)

Two **new** fields:

| Field | Type | Notes |
|---|---|---|
| `fte_v2_complete` | bool | Distinct from existing `fte`. False until the debut publish succeeds. |
| `tutorial_state` | object | Nested object below. |

`tutorial_state` shape:

```python
{
  "step": "team_select" | "username" | "situation" | "set_lineup" | "in_game" | "complete",
  "team_pick": "<team_id>" | None,
  "started_at": <ISO datetime>,
  "completed_at": <ISO datetime> | None,
}
```

Existing `fte` flag is **preserved** (don't break the old flow's marker).

### 2.2 Community highlights entry schema (`community_highlights_collection`)

Add new `entry_type: "debut"` variant:

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
  "secondary_color": str
}
```

Renders with gold metallic border (see Section 5.4).

---

## 3. Migration

Script: `scripts/migrate_fte_v2.py`

| Step | Logic |
|---|---|
| 1 | For every user document, set `fte_v2_complete: False` and initialize empty `tutorial_state: { step: "team_select", team_pick: None, started_at: now, completed_at: None }`. |
| 2 | For every user with **at least one franchise record** (any document in `franchises_collection` matching `user_id`), set `fte_v2_complete: True`. These users are grandfathered and never see the new tutorial. |
| 3 | Run dry against staging first; print counts (total users, grandfathered, will-see-tutorial). Coach approves before production run. |

**Existing alpha users with `fte: true`:** if they have no franchise records, they DO see the new tutorial. That's the intended behavior per Q7.

---

## 4. Backend changes

### 4.1 `BackEnd/api/auth_routes.py`

| Change | Detail |
|---|---|
| `signup` endpoint | Set `fte_v2_complete: False`, init empty `tutorial_state`. Keep existing `fte: True`. |
| `GET /api/auth/me` response | Include `fte_v2_complete` and `tutorial_state` in `UserResponse`. |
| NEW: `POST /api/auth/tutorial-advance` | Body: `{ step, team_pick? }`. Server validates **forward-only** transition (rejects backward). Updates `tutorial_state`. |
| NEW: `POST /api/auth/tutorial-complete` | Sets `fte_v2_complete: True`, `tutorial_state.step = "complete"`, `tutorial_state.completed_at = now`. Called **only after** debut publish succeeds. |

### 4.2 `BackEnd/api/api.py` — `init_game`

Extend with optional `tutorial_initial_state` payload:

```python
class InitGameRequest(...):
    ...
    mode: str  # add "tutorial" as valid value
    tutorial_initial_state: Optional[dict] = None
    tutorial_shot_threshold_overrides: Optional[dict] = None  # {"user": 10, "computer": 210}
```

When `mode == "tutorial"`:
- Bypass standard Q1 / 0-0 boot
- Write all values from [fte_inject_state.md §1](fte_inject_state.md) directly into `game_state`, `team.team_attributes`, per-player rows
- Apply shot_threshold overrides via `init_team_attributes` extension (4.3)
- Set `game_stats_initialized: True` before first turn
- Force first turn type to SIP via the existing timeout-resume path ([main.py:381-407](BackEnd/main.py#L381-L407))
- Apply strategy_settings overrides per [fte_inject_state.md §2](fte_inject_state.md)
- Apply `points_by_quarter` per [fte_inject_state.md §4](fte_inject_state.md)
- Load roster + apply Section 5 stat overlay (see 4.4)

### 4.3 `BackEnd/models/team_manager.py` — `init_team_attributes`

Add optional `shot_threshold_override` parameter. When set, bypass the random 10-210 roll and use the override. Only invoked from the tutorial init path.

### 4.4 NEW: `BackEnd/data/tutorial_rosters.py`

Encodes the two universal stat templates from [fte_inject_state.md §5](fte_inject_state.md):
- `USER_TEAM_STAT_TEMPLATE` — dict of position → stat block
- `COMPUTER_TEAM_STAT_TEMPLATE` — same shape

Plus a helper:
```python
def apply_tutorial_roster(team_name: str, side: "user" | "computer") -> list[Player]:
    """
    1. Load all players for `team_name` from players_collection.
    2. Compute / read position_ratings for each player.
    3. For each position slot (PG, SG, SF, PF, C), stack-rank by position_ratings[pos] desc.
    4. Top-ranked per position = Starting; next 7 = Backup 1..7 (overall rank by best-position score).
    5. Apply USER_TEAM_STAT_TEMPLATE or COMPUTER_TEAM_STAT_TEMPLATE stat overlay onto the ranked list.
    6. Return Player objects with player.stats["game"] populated.
    """
```

The names in [fte_inject_state.md §5.1-5.8](fte_inject_state.md) are documentation of *expected* starters once derivation runs. If derivation produces a different starter for any team, surface the diff for Coach review before shipping.

### 4.5 NEW: `BackEnd/api/community_highlights_routes.py` — debut publish

| Change | Detail |
|---|---|
| Add `entry_type: "debut"` to allowed entries in `community_highlights.py` push helper | Schema 2.2 above. |
| NEW: `POST /api/community/debut` | Authenticated. Body: `{ user_team_name, opponent_name, user_score, opponent_score, user_won }`. Server reads `username` + colors from user doc + team manifest. Writes entry. |

### 4.6 `BackEnd/api/api.py` — finalizeGame path

`mode == "tutorial"` follows the existing `single` path (no franchise/tournament writes). Game doc deleted via existing `/api/games/delete-completed-single` precedent.

---

## 5. Frontend changes

### 5.1 Routing & entry decision — `FrontEnd/static/js/shared/authBarInit.js`

| Change | Detail |
|---|---|
| Replace existing `if (fte === true) runFTE()` block | New decision: `if (!user.fte_v2_complete) routeToTutorial(user.tutorial_state.step)`. |
| `routeToTutorial(step)` | Navigates to the page corresponding to the step. If the user is already on that page, no-op. If on a "wrong" page, redirect. |
| Old `runFTE()` + 4-step modals | **Removed.** Sammy username modal extracted to a standalone component (see 5.6). |
| `PAGES_WITHOUT_AUTH_BAR` | Add tutorial pages to the skip list (court is already there; add tutorial-situation if it's a new page). |

### 5.2 Team-select — `FrontEnd/static/franchise-select-team.html` + `.js`

Add **early branch** on URL param `?mode=tutorial`:

| Behavior | Tutorial mode | Franchise mode (existing) |
|---|---|---|
| Team-card click | `POST /api/auth/tutorial-advance` with `{ step: "username", team_pick: <id> }`, then navigate to username step | Existing franchise creation path (unchanged) |
| Page header | "Pick your program, Coach." (or similar — confirm copy) | Existing copy (unchanged) |
| Back button | None | Existing |

Implementation: an early `if (urlMode === "tutorial") { wireTutorialHandlers(); return; }` at top of `init()` so the franchise code path is untouched when tutorial.

### 5.3 Username step — modal extracted

Extract the username modal currently inside `authBarInit.js` lines 87–266 into `FrontEnd/static/js/shared/usernameModal.js`. Restyled per design system (Section 5.6). Called from the tutorial flow controller after team-select.

On success: `POST /api/auth/set-username`, then `POST /api/auth/tutorial-advance` with `{ step: "situation" }`, then navigate to situation page.

### 5.4 Situation card — NEW page `FrontEnd/static/tutorial-situation.html`

Single screen, single modal in the design-system style with Sammy. Copy (per Coach):

> "Ok Coach, let's play ball. You're playing **{opponent_team_name}**, and the score is tied 60-60 with 4 minutes remaining. Let's win this!"

Where `opponent_team_name` is `"Xavien"` unless the user picked Xavien, in which case `"South Lancaster"`.

CTA: "Set Lineup" → `POST /api/auth/tutorial-advance` with `{ step: "set_lineup" }`, then navigate to `set-lineup.html?mode=tutorial`.

### 5.5 Set-lineup — `FrontEnd/static/set-lineup.html` + `.js`

Add **early branch** on URL param `?mode=tutorial`:

| Behavior | Tutorial mode | Existing modes |
|---|---|---|
| On load | Call `/api/autoset-lineup` immediately with user team + tutorial roster context. Pre-populate the 5 slots. | Existing on-demand autoset |
| Attribute tooltips | **Activate** `initAttributeTooltips()` on the attribute headers (currently loaded but never called — [attributeTooltips.js](FrontEnd/static/js/shared/attributeTooltips.js)) | Leave as-is (do not change for non-tutorial modes in this PR) |
| Sammy modal | Show ONE modal on first paint: "I've set your lineup, feel free to make any changes as you see fit." | None |
| CTA (Play button) | `POST /api/auth/tutorial-advance` with `{ step: "in_game" }`, then navigate to `court.html?mode=tutorial&home=<user_team>&away=<opponent>&my_team=home` | Existing |
| Back link | **None** (per Coach: user is locked in after team-select) | Existing |

### 5.6 Sammy modal design system — NEW `FrontEnd/static/css/sammy-modal.css` + JS helper

| Item | Detail |
|---|---|
| Visual baseline | Mirror chrome of standard post-game modal ([gameCompletionPopup.js](FrontEnd/static/js/phaser/utils/gameCompletionPopup.js) — eyebrow, dark background, orange accents) |
| Sammy placement | Headshot at top-left or top-center (consistent across all tutorial modals) |
| Modal types using it | username, situation card, set-lineup intro, tutorial post-game |
| Reusable component | `showSammyModal({ eyebrow?, body, image, ctaLabel, onCta })` — single API for all tutorial modals |

Old `FrontEnd/static/css/fte.css` (white background style) is **removed** along with the 4-step FTE.

### 5.7 In-game — `FrontEnd/static/court.html` + `bootGame.js`

| Change | Detail |
|---|---|
| URL convention | `?mode=tutorial` added alongside existing `franchise` / `tournament` / no-mode-single |
| `getMode()` in [bootGame.js:43-47](FrontEnd/static/js/phaser/bootGame.js#L43-L47) | Add `"tutorial"` branch, returns `"tutorial"` |
| `init_game` call payload | Include `tutorial_initial_state` and `tutorial_shot_threshold_overrides` per Section 4.2 |
| Tutorial-specific game writes | None beyond standard `single` (no franchise/tournament hooks) |
| Phaser canvas | Unchanged (1229×768 hard-coded constraint preserved) |

### 5.8 Tutorial post-game modal — `gameCompletionPopup.js`

Add `mode === "tutorial"` branch. Layout (per Coach, vertical):

```
[Eyebrow: "Your Debut"]
[Message: win → "Congrats on winning your first game Coach!"
          loss → "That was a tough one Coach -- but we're confident you'll bounce back."]
[Final Score: <User Team> <user_score> — <opp_score> <Opponent Team>]
[POTG: header / name / image / PTS · REB · AST · DEF%]
[Go To Locker Room] ← matches existing button copy
```

No Box Score button. No franchise-PGPC button. Routes to `/mode-select.html`.

On CTA click:
1. `POST /api/community/debut` (Section 4.5)
2. On success: `POST /api/auth/tutorial-complete` (Section 4.1)
3. Navigate to `/mode-select.html`
4. (Existing `delete-completed-single` cleanup runs per single-mode precedent)

If debut publish fails: retry once; on second failure, log + still mark `fte_v2_complete: true` (do not strand the user in tutorial limbo). Coach surfaces as alert in ops dashboard.

### 5.9 Mode-select Live Feed — `FrontEnd/static/mode-select.js`

Add render branch for `entry_type: "debut"`. Visual: standard row layout + **gold metallic border** on the entry container. Non-clickable (no hover state, no click handler).

For the gold: source from existing in-app metallic gold treatment (championship/trophy CSS). Audit needed during build to identify the canonical token.

---

## 6. Files touched / created — summary

### New files

| File | Purpose |
|---|---|
| `BackEnd/data/tutorial_rosters.py` | Two universal stat templates + apply helper |
| `BackEnd/scripts/migrate_fte_v2.py` | One-time migration |
| `FrontEnd/static/tutorial-situation.html` | Situation card page |
| `FrontEnd/static/js/shared/usernameModal.js` | Extracted from authBarInit |
| `FrontEnd/static/js/shared/sammyModal.js` | Reusable Sammy modal helper |
| `FrontEnd/static/css/sammy-modal.css` | Design-system Sammy modal styling |
| `FrontEnd/static/js/tutorial-router.js` | Step-based routing helper |

### Files modified

| File | What changes |
|---|---|
| `BackEnd/api/auth_routes.py` | New `fte_v2_complete` + `tutorial_state` fields; new advance + complete endpoints |
| `BackEnd/api/api.py` | `init_game` extension for tutorial state injection |
| `BackEnd/api/community_highlights_routes.py` | New `POST /api/community/debut` endpoint |
| `BackEnd/community_highlights.py` | Accept new `entry_type: "debut"` |
| `BackEnd/models/team_manager.py` | `init_team_attributes` shot_threshold override |
| `BackEnd/models/game_manager.py` | Tutorial-mode initial-state hydration |
| `FrontEnd/static/js/shared/authBarInit.js` | Replace `runFTE()` with tutorial routing decision; remove 4-step modals |
| `FrontEnd/static/franchise-select-team.html` + `.js` | `?mode=tutorial` early branch |
| `FrontEnd/static/set-lineup.html` + `.js` | `?mode=tutorial` early branch + tooltips activation |
| `FrontEnd/static/js/phaser/bootGame.js` | `getMode()` + tutorial init payload |
| `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` | Tutorial-mode branch |
| `FrontEnd/static/mode-select.js` | Debut entry render branch |
| `FrontEnd/static/css/mode-select.css` (or wherever Live Feed styles live) | Gold metallic border for debut entries |

### Files deleted

| File | Why |
|---|---|
| `FrontEnd/static/css/fte.css` | Old white-background FTE modal styling — fully replaced by `sammy-modal.css` |

---

## 7. Phasing / PR plan

Recommend **two PRs** to keep review tractable:

### PR 1 — Backend + schema + migration (no user-visible change)

- Schema additions (Section 2)
- Migration script (Section 3, dry-run first)
- `init_game` extension (Section 4.2)
- `init_team_attributes` extension (Section 4.3)
- Tutorial rosters module (Section 4.4)
- Community highlights debut entry (Section 4.5)
- New auth endpoints (Section 4.1)

Ship behind absence of frontend wiring — nothing fires yet. Safe to merge and verify in staging without flipping user behavior.

### PR 2 — Frontend funnel + cutover

- All frontend changes (Section 5)
- Delete old FTE modals + CSS
- Cutover: `authBarInit.js` decision flip

Merging this PR is the cutover moment. Old FTE goes away; new FTE goes live for all non-grandfathered users.

---

## 8. Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Tutorial state injection corrupts a single/franchise/tournament game (cross-contamination) | All inject logic gated on `mode === "tutorial"`. Existing modes never hit the new branches. PR 1 includes regression smoke test for single/franchise mode init. |
| R2 | Migration grandfathers wrong users | Dry-run on staging; print counts; Coach approves before prod. Idempotent script (safe to re-run). |
| R3 | Position-rating derivation puts a non-expected player in Starting PG slot for some team | During PR 1 build, surface a diff of derived starters vs [fte_inject_state.md §5](fte_inject_state.md) named players; Coach reviews and approves or asks for attribute tweaks. |
| R4 | Debut publish fails after user finishes game → user stuck in tutorial | Retry once; on second failure, still mark `fte_v2_complete: true` and log alert. User not stranded. |
| R5 | Two-tab race during step advancement | Server forward-only step validation rejects backward transitions; both tabs converge on furthest-reached step. |
| R6 | Mid-game abandonment leaves a tutorial game_id orphaned in `games_collection` | Existing `delete-completed-single` only runs on completion. Add cleanup: any tutorial game_id older than 24h with `tutorial_state.step !== "complete"` gets deleted by a nightly job. (Or: tolerate orphans; volume is small.) |
| R7 | Removing old `fte.css` breaks any non-tutorial usage | Grep for `fte.css` references before deletion. Confirmed at build time. |
| R8 | Sammy modal restyle clashes with existing in-game post-game modal | The post-game modal IS the design baseline (HB2) — restyle inherits from it, can't clash. |
| R9 | Phaser canvas tutorial game runs poorly on smaller desktop monitors | 1229×768 is fixed; users on sub-1229 displays see horizontal scroll. Desktop-only is accepted (Q10). Document min-width in onboarding messaging if needed. |

---

## 9. Testing strategy

Per project memory: pytest is conditionally allowed on staging DB only, never delete/replace existing docs. Test approach:

| Surface | Test approach |
|---|---|
| Migration script | Run against staging snapshot. Print before/after counts. Coach signs off. |
| `init_game` tutorial branch | Manual: boot tutorial via curl with full `tutorial_initial_state`; verify game_state mirrors [fte_inject_state.md](fte_inject_state.md) exactly. |
| Existing single/franchise/tournament init | Manual smoke after PR 1: boot one game of each mode, verify no behavior change. |
| Tutorial state advance forward-only | Pytest (staging): create test user, advance step forward, attempt backward, expect 400. |
| Debut publish + render | Manual end-to-end: complete tutorial, verify gold-border row appears on mode-select Live Feed and is non-clickable. |
| Grandfathering | Manual: log in as existing alpha user with franchise records — should land on mode-select with no tutorial fired. |
| Tutorial full flow | Manual end-to-end on staging: new signup → tutorial → debut publish → mode-select land. Do this for each of the 8 team picks (specifically including Xavien pick to verify South Lancaster fallback). |

No new automated UI test coverage required for this PR (matches project precedent).

---

## 10. Open questions / parking lot

None blocking. Surface during build:

| # | Item | When to resolve |
|---|---|---|
| P1 | Exact gold metallic CSS token for debut Live Feed border | During PR 2 build — audit existing championship/trophy CSS |
| P2 | Derived-starters vs named-starters diff per team | During PR 1 build — surface the diff for Coach review |
| P3 | Team-select page header copy in tutorial mode | Pre-PR 2 — coach drops final copy |
| P4 | Orphan tutorial game_id cleanup (R6) — nightly job vs tolerate | Pre-merge of PR 1 — coach decision |
| P5 | Should `fte: true` be cleared in tandem with `fte_v2_complete: true`? Or kept independent? | Pre-PR 1 — minor cleanup decision |
