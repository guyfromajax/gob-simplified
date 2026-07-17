## Steal System

> **Scope (reframed 2026-06-13):** This doc owns **steal resolution and the post-steal routing decision** (what happens immediately after a defender records a steal). The **steal → Fast Break** path was migrated to the UESS-schema **`after_steal`** Fast Break play in May 2026; its mechanics now live in **[`Fast_Break_System.md`](Fast_Break_System.md)** (§ "After Steal") and `BackEnd/engine/after_steal_fast_break.py`. The legacy bespoke "steal entry" movement + `animateStealEntry()` described in older versions of this doc are **superseded/removed** — see "Steal → Fast Break" below.

---

## Overview

When a defender records a steal, the system:

1. **Records the steal** and attaches the ball to the stealer (the defender who made the steal).
2. Stores **`game_state["last_stealer"]`** (the stealer) and **`game_state["last_stealer_coords"]`** (position at the moment of the steal).
3. Makes **one** routing roll (potential cutoffs × stealing-team aggression) to pick the next state:
   - **`FAST_BREAK`** → the **`after_steal`** Fast Break play (UESS schema).
   - **`HCO`** → a half-court possession, preceded by a backend **steal-HCO setup** repositioning of the stealer + other players.

The stealing team is **`def_team`** at resolution time (the defense recorded the steal). The roll uses **their** aggression plus how many of the **victim team's** five on-floor players can challenge the stealer’s drive (see below) — *not* the old aggression-only slider table.

---

## Steal resolution & next-turn routing

**Where steals resolve:** `_check_steal_attempt()` in `BackEnd/engine/phase_resolution.py` runs in FCP, HCT, and HCO turns. On a steal it sets `game_state["last_stealer"]` and `game_state["last_stealer_coords"]`. The routing roll happens in:
- `resolve_turnover_logic()` when `turnover_type == "STEAL"` (HCO steals),
- the **FCP** steal branch (`resolve_full_court_press_logic`),
- the **HCT** steal branch (`resolve_half_court_trap_logic`).

**The single routing roll (potential cutoffs × aggression):**

Implemented in `BackEnd/engine/steal_fast_break_routing.py` (`choose_steal_next_offensive_state`). Runs at the end of the steal turn after `last_stealer` / `last_stealer_coords` are set.

1. **Shot spot** — same rim-band sample as after-steal drive (`sample_after_steal_shot_spot`: basket_x ± 2–4, y 19–31).
2. **Potential challengers** — count of victim-team players who can win an AG **sprint** race to a meet on stealer → shot spot that is **x-ahead** of the stealer (`cutoff_meet_point` + `steal_meet_x_ahead_valid`). **No** path-corridor pre-filter (corridor remains for drive/shot contest elsewhere). High-AG players starting behind can still count if they can angle into an x-ahead meet in time.
3. **Bucket** the count: **0 / 1 / 2+**.
4. **Aggression** — stealing team's Game Plan aggression **0–4** (Slow It Down may force 0).
5. **P(FAST_BREAK)** from `STEAL_FB_PROB_BY_POTENTIAL_CUTOFFS` (`fast_break_constants.py`):

| Potential cutoffs | Agg 0 | Agg 1 | Agg 2 | Agg 3 | Agg 4 |
|---|---|---|---|---|---|
| **2+** | 0% | 10% | 20% | 30% | 40% |
| **1** | 0% | 20% | 40% | 60% | 80% |
| **0** | 50% | 80% | 85% | 90% | 99% |

- **Contrast:** DREB (missed-shot) fast breaks still use the **rebounding team's `fast_breaks`** slider via `fast_break_probability_from_slider` / `SLIDER_TO_FAST_BREAK_PROB` — see [`Fast_Break_System.md`](Fast_Break_System.md).

`game_manager` flips possession and routes to the chosen state. When `FAST_BREAK`, the Fast Break play key is **`after_steal`** (no DREB outlet pass).

---

## Steal → Fast Break (`after_steal`) — UESS migrated

Steal-initiated fast breaks are resolved by **`resolve_after_steal_fast_break()`** (`BackEnd/engine/after_steal_fast_break.py`) and rendered from backend-emitted schema steps (`after_steal_fast_break_step_emitter.py`). `resolve_fast_break_logic()` short-circuits to this resolver whenever `fb_play_key == AFTER_STEAL` (i.e. all steal entries), so the old steal-entry/outlet/stopper code below it is bypassed.

**Current spec lives in [`Fast_Break_System.md`](Fast_Break_System.md) § "After Steal."** In brief: the stealer drives toward `basket_x ± random(2,3)`, all five defenders sprint to a single spot, traversal timing is AG-based (first-arriver determination + freeze), and a contested/uncontested check resolves the shot. Make announcements read "Fast Break Score!".

> **Legacy (removed):** Earlier versions of this doc described a bespoke "Steal Entry" movement (stealer moves 5–10 x toward basket, ±4 y) followed by a DREB-style "defender ahead AND within ±6 y" defensive-stop-vs-shot check, animated by `animateStealEntry()`. That path is **superseded**: `animateStealEntry()` was removed during the after-steal UESS migration (`FrontEnd/static/js/phaser/animation/fastBreak.js`), the `STEAL_ENTRY_*` constants are no longer imported there, and the legacy steal-entry block in `resolve_fast_break_logic` is unreachable for steals (the `after_steal` short-circuit returns first). The `STEAL_ENTRY_MOVE_*` / `STEAL_ENTRY_Y_*` constants in `fast_break_constants.py` are now legacy/unused.

---

## Steal → HCO setup

When the routing roll lands on **HCO**, the *next* HCO turn runs a backend **steal-HCO setup** that repositions the stealer and everyone else before the HCO skeleton. This is computed in **`resolve_half_court_offense_logic()`** (`BackEnd/engine/phase_resolution.py`, ~L4820) when `last_stealer` is set and `offensive_state == "HCO"`.

**Stealer (becomes the HCO ball handler):**
- Moves **away** from the offense basket: **3–7** x spots (`STEAL_HCO_SETUP_MOVE_X_MIN/MAX`), **±3** y (`STEAL_HCO_SETUP_MOVE_Y_RANGE`), y clamped **3–47** (`STEAL_HCO_SETUP_Y_MIN/MAX`).
- Direction is the opposite of attacking the basket (home offense → toward x=10; away offense → toward x=90).
- Start position uses `last_stealer_coords` when available (position at the steal), else the stealer's current `coords`.

**PG repositioning (only when the ball handler is *not* the PG):**
- The offensive PG moves to a spot relative to the ball handler: **±6** y from the ball handler (clamped 4–46) and **3–9** x toward the offense basket from the ball handler (x clamped 4–97). This is a bespoke branch separate from the "other players" movement below.

**All other players (remaining offense + all defense):**
- Move **15–30** x toward the new offense basket (`STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MIN/MAX`), **±6** y (`STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_Y_RANGE`), x clamped 4–97, y clamped **4–46** (`STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MIN/MAX`).

The backend stamps `roles["is_steal_hco_setup"] = True` plus `ball_handler_hco_setup_x/y`, `ball_handler_hco_setup_move_x/y`, `other_players_hco_setup_movements`, `hco_setup_x_direction`, and `ball_handler_id`, then **clears** `last_stealer` / `last_stealer_coords` / stored skeleton data so the setup runs only once.

> **⚠️ Frontend render status (verify before relying on this).** The dedicated frontend animator `animateStealHCOSetup()` and any consumption of `is_steal_hco_setup` / `ball_handler_hco_setup_*` / `other_players_hco_setup_movements` have been **removed** — there are no references to these fields anywhere in `FrontEnd/`. The backend still computes and stamps the setup positions on `roles`, but the frontend no longer reads them, so the dedicated steal-HCO-setup animation is not played; the post-steal HCO turn renders through the standard HCO pipeline. The backend setup-coord computation is therefore a **cleanup candidate** (compute-but-unrendered) — tracked as `[CODE-CLEANUP]` in `projects/bugs.md`. Re-confirm against `resolve_half_court_offense_logic` and the HCO animation path before building on it.

---

## Constants

`BackEnd/constants/fast_break_constants.py` (mirrored on the frontend in `FrontEnd/static/js/phaser/constants/fastBreakConstants.js`):

**Steal-HCO setup (live):**
- `STEAL_HCO_SETUP_MOVE_X_MIN = 3`, `STEAL_HCO_SETUP_MOVE_X_MAX = 7`
- `STEAL_HCO_SETUP_MOVE_Y_RANGE = 3`, `STEAL_HCO_SETUP_Y_MIN = 3`, `STEAL_HCO_SETUP_Y_MAX = 47`
- `STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MIN = 15`, `STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MAX = 30`
- `STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_Y_RANGE = 6`, `STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MIN = 4`, `STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MAX = 46`

**Steal-entry (legacy / unused by `after_steal`):**
- `STEAL_ENTRY_MOVE_X_MIN = 5`, `STEAL_ENTRY_MOVE_X_MAX = 10`, `STEAL_ENTRY_MOVE_Y_RANGE = 4`, `STEAL_ENTRY_Y_MIN = 3`, `STEAL_ENTRY_Y_MAX = 47` — retained in `fast_break_constants.py` but no longer drive the rendered after-steal break.

---

## Key Files

**Backend:**
- `BackEnd/engine/phase_resolution.py`
  - `_check_steal_attempt()` — steal detection; sets `last_stealer` + `last_stealer_coords` (FCP/HCT/HCO).
  - `resolve_turnover_logic()` — HCO STEAL routing roll (`def_team` aggression).
  - FCP / HCT steal branches — same `def_team` aggression routing roll.
  - `resolve_half_court_offense_logic()` (~L4820) — steal-HCO setup positioning.
  - `resolve_fast_break_logic()` (~L1056) — short-circuits steals to the `after_steal` resolver.
- `BackEnd/engine/after_steal_fast_break.py` — steal → Fast Break resolution (current spec).
- `BackEnd/engine/after_steal_fast_break_step_emitter.py` — schema emitter (pure renderer) for the after-steal break.
- `BackEnd/utils/shared.py` — `fast_break_probability_from_slider()`, `SLIDER_TO_FAST_BREAK_PROB`.
- `BackEnd/constants/fast_break_constants.py` — steal-HCO-setup (live) + steal-entry (legacy) constants.

**Frontend:**
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` — `MIGRATED_FB_PLAYS` includes `after_steal`; consumes schema steps for the break.
- `FrontEnd/static/js/phaser/constants/fastBreakConstants.js` — mirrored constants.

**Related docs:**
- [`Fast_Break_System.md`](Fast_Break_System.md) — § "After Steal" (FB path spec), DREB vs steal entry probability sources.
- [`HCO_Turn_Resolution_System.md`](HCO_Turn_Resolution_System.md) — HCO turn resolution the steal-HCO path feeds into.
