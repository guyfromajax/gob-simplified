# Animation System Refactor

> **Status:** Discovery / scoping — not yet a plan. This doc is the foundation for redesigning the animation system into something scalable. Started 2026-05-09.
>
> **Goal:** A single, simple, scalable (SS&S) animation system that handles every turn type uniformly, instead of the current fragmented per-turn-type implementations. We don't have a plan yet — we're aligning on what the system needs to handle first.
>
> **Predecessors (reference, not extension):**
> - [`Fast_Break_Refactor.md`](Fast_Break_Refactor.md) — fast-break-specific work-in-progress; its incremental phasing is being paused/superseded by this refactor.
> - [`Movement_Rate_Refactor.md`](Movement_Rate_Refactor.md) — shipped May 2026; introduced AG-driven timing and the per-waypoint `game_seconds` pattern.

---

## Step 1 — Inventory of every turn type

Every animation surface in the game, grouped by category. This is the canonical list the new system has to support uniformly.

### Primary plays (the offense's main action)

| Turn type | Code (back / front) | Notes |
|---|---|---|
| **HCO** — Half-Court Offense | `phase_resolution.py` (HCO branch); `turnAnimation.js:playTurnAnimation`; `HCOAnimationSystem.js` | Default offensive turn. Skeleton-driven (set-play steps). |
| **HCT** — Half-Court Trap | `dynamic_hct.py`; `turnAnimation.js` (same step loop) | Independent turn type. Resolves to shot, foul, steal, dead-ball turnover, or transition into HCO. |
| **FCP** — Full-Court Press | shares HCO step-loop wiring; `turnAnimation.js`; `FCP_SETUP_POSITIONS` constants | Independent turn type. Same outcome space as HCT. |
| **Fast Break** | `fastBreak.js`; `phase_resolution.py:resolve_fast_break_logic`; `rim_runner_fast_break.py` | Has 4 sub-variants with distinct animation paths (see below). |

#### Fast Break sub-variants

These are different enough in animation that they should be treated as distinct surfaces:

| Sub-variant | Trigger | Animation path |
|---|---|---|
| **Covert Release** | DREB + `pending_dreb_fb_play_key == "covert_release"` | `animateOutletPhase` (mostly no-op) → `animateDefensiveStop` / shot phases |
| **Rim Runner** | DREB + `pending_dreb_fb_play_key == "rim_runner"` | `animateRimRunnerBurstPhase` → lane pass / interception / bat-OOB / hold-up / outlet-denied |
| **Triangle** | DREB + `pending_dreb_fb_play_key == "triangle"` | Drafts off RR setup; then 7 internal branches (rr_post, corner_three, bh_wing_three, bh_drive, drive_rr_feed, drive_corner_kick, enter_hco) |
| **After Steal** | Steal during HCO/HCT/FCP turn | `animateStealEntry` → standard FB shot/defensive-stop |

### Inbounds (positioning between plays)

| Turn type | Trigger | Animation path |
|---|---|---|
| **BIP** — Baseline Inbound Pass | `next_play_type == "BASELINE_INBOUND"` (made shot, made FT, etc.) | `PassAnimationSystem`; sets up new offense receiving inbound |
| **SIP** — Side Inbound Pass | `next_play_type == "SIDE_INBOUND"` (turnover, dead ball, OOB) | Same system, different setup positions |

### Special turns (interrupt or extend normal flow)

| Turn type | Trigger | Animation path |
|---|---|---|
| **Free Throw** | `next_play_type == "FREE_THROW"` | `freeThrow.js`; `FreeThrowAnimationSystem.js` |
| **OREB** — Offensive Rebound (putback) | `result_type == "PUTBACK_MAKE" / "PUTBACK_MISS"` from a prior MISS turn | Separate turn appended after the missing shot turn; uses `ReboundAnimationSystem.js` plus a putback shot animation |
| **DREB** — Defensive Rebound | After a missed shot when the rebounder is on the defensive team. Currently bundled inside the MISS turn (rebounderId field); **promoted to its own turn type as part of the SS&S animation refactor** (see `Animation_System_Updated.md`). | Symmetric with OREB structurally but no putback shot — rebounder captures ball, possession flips, next turn is offensive setup or fast break. |
| **Timeout** | `result_type == "TIMEOUT"` (called from sideline, foul-out, end-of-quarter ad-break, etc.) | Pause + UI overlay; little or no sprite animation |
| **Opening Tip** | First turn of game / quarter | `openingTip.js`; jump-ball animation, possession assignment |

---

## Resolved decisions

- **HCT, FCP independent turn types.** Distinct from HCO. Each can resolve to shot, foul, steal, dead-ball turnover, or HCO entry.
- **Fast Break unification — open.** Likely revisited once we break FB into steps with per-step payloads.
- **BIP / SIP independent turn types.** Open to revisiting. BIP is the entry to HCO/HCT/FCP.
- **Timeout stays in the animation system for now.** Open to removal later.
- **Unit of animation = step, per turn type.** Each turn type has its own kind of step (HCO uses skeleton steps; HCT is more dynamic).

---

## Things explicitly NOT on the list (and why)

| Excluded | Why |
|---|---|
| Steal, Foul, Block, Turnover (events) | These fire *within* turns and produce result-type changes / route to next turn — they don't have standalone turn types of their own. They do have visual effects (ball drop, foul flash, etc.) but ride on the parent turn's animation. |
| End-of-quarter | A state transition, not a turn. Has an announcement banner but no sprite animation. |
| HCO set plays / playcalls (e.g. "5-0 Motion", "Misdirection Three") | Variants of HCO turns — same animation system, different skeleton step content. Not separate turn types. |
| Jump ball (mid-game) | Currently treated as a flavor of Opening Tip. May warrant separate handling if we ever animate mid-game jump balls. |

---

---

## Step 2 — Current payload per step, per turn type

What each turn type currently emits at the end of each step. Goal: surface inconsistencies before we design the unified shape.

**Confidence key:** ✅ verified from code; ⚠️ partial / inferred; ❓ not audited yet.

### HCO ✅
Per-step (`skeleton.steps[i]`):
- `timestamp` (ms)
- `pos_actions{POS: {location, action}}`
- `events[]`

Turn-level (alongside the step list):
- `step_clock_seconds[]` (parallel array — clock seconds per step)
- `bringup_per_player_seconds{POS: seconds}` (BIP→HCO bring-up only)
- `animations[]` (per-player movement records)
- `position_snapshots[]` (checkpoints with positions per player)

### HCT ⚠️
Same shape as HCO (uses the same `skeleton` + `step_clock_seconds` structure). Plus:
- Per-waypoint `game_seconds` on `animations[i].movement[k]` (Movement Rate Refactor Phase 3a).

### FCP ⚠️
Same shape as HCO/HCT.

### Fast Break ⚠️
**No real "step" structure on the backend.** Phase-based on the frontend instead.
Turn-level:
- `animations[]` per player (`movement[]` with `timestamp`, `coords`, `action`, `game_seconds`, `hasBallAtStep`, `duration` (hardcoded 800 ms))
- `roles{}` (ball_handler, defense, outlet_passer, outlet_receiver, etc.)
- `fast_break = True`, `fast_break_play` (covert_release / rim_runner / triangle / after_steal)
- `hold_up`, `stopper_id`, `shot_spot`, `defender_spot` (when applicable)
- `roles.rim_runner_burst_phase{}` (RR / Triangle only) — separate schema with `rr_to`, `receiver_to`, `outlet_defender_to`, `other_players[]`, each with their own `game_seconds` (Phase 4b).

### BIP ❓
Believed:
- `next_play_type`, `current_turn = "BASELINE_INBOUND"`, `next_defensive_setup` (FCP/HCT/null)
- Setup positions per player (probably from `FCP_SETUP_POSITIONS` / `HCT_SETUP_POSITIONS` / HCO equivalents)
- Pass animation data
- *Not audited — needs a pass before we redesign.*

### SIP ❓
Same family as BIP. Not audited.

### Free Throw ❓
Believed:
- `attempts[]` (per-shot results)
- Shooter, lane positions
- *Not audited.*

### OREB ❓
- Separate turn appended; `result_type = "PUTBACK_MAKE" / "PUTBACK_MISS"` (or related)
- Single putback animation
- *Not audited.*

### Opening Tip ❓
- Jump-ball positioning + winner
- *Not audited.*

### Timeout ❓
- Likely just `result_type = "TIMEOUT"` + duration, minimal animation payload
- *Not audited.*

---

## Inconsistencies already visible

Before any deep audit:

1. **HCO/HCT/FCP** carry per-step clock data (`step_clock_seconds[]`) and a per-step skeleton — Fast Break has neither. FB is "phases on the frontend," not steps.
2. **Per-player game_seconds** lives in different places: `animations[i].movement[k].game_seconds` (HCT, FB animations[]) vs `roles.rim_runner_burst_phase.X.game_seconds` (FB burst phase) vs `bringup_per_player_seconds{POS: seconds}` (HCO bring-up).
3. **The duration field**: HCO/HCT have variable per-step timestamps; FB animations have a hardcoded `duration: 800` ms regardless of distance.
4. **Setup positions**: BIP/SIP have one mechanism; HCO bring-up has another (`bringup_per_player_seconds`); FB outlet phase has a third (essentially a no-op).

The non-FB turn types (BIP, SIP, FT, OREB, Opening Tip, Timeout) need to be audited before we can say what the full shape of inconsistency is.
