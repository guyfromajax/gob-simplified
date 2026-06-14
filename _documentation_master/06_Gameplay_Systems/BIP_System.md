## BASELINE_INBOUND (BIP) System ✅ **COMPLETE** (January 2025; re-verified + updated June 2026)

> **UESS migration status:** BIP now also emits unified **`animation_steps[]`** — a 2-step schema turn (Step 1 = setup walk-in: SF carries ball to baseline while everyone moves to BIP destinations; Step 2 = inbound pass: SF→PG while the other 8 continue) built by `transition_bridge.build_bip_animation_steps` inside `setup_baseline_inbound()`. Schema-carrying BIP turns play through `animationPlayback.playTurn()`; the `handleBaselineInbound()` → `runInboundSetup()` flow described below is the legacy path. A position-snapshot (`bip_inbound_setup`) is attached via `position_snapshot_ledger`.

**Base Constants**

1. **Trigger Conditions**:
   - After any made shot: HCO MAKE, PUTBACK_MAKE, Fast Break MAKE, Free Throw MAKE
   - Quarter starts (Q2, Q3, Q4): BASELINE_INBOUND at beginning of quarter
   - Next turn is always `BASELINE_INBOUND`
   - Handles player positioning and inbound pass animation before next offensive sequence

2. **Next Turn Scenarios**:
   - **HCO** (Normal Inbound): `next_defensive_setup=None`, defensive players retreat to midcourt
   - **HCT** (Half Court Trap): `next_defensive_setup="HCT"`, defensive players go to trap positions
   - **FCP** (Full Court Press): `next_defensive_setup="FCP"`, defensive players go to press positions

3. **Coordinate System**:
   - **Home Orientation**: `HCO_STRING_SPOTS` coordinates in home team orientation
   - **Inbound Spots**: Home offense uses `inbound_left` (x=3), away offense uses `inbound_right` (x=97)
   - **Coordinate Flipping Formula**: backend `getAwayTeamCoords` uses `x = 100 - x`; legacy frontend flip helpers in `turnAnimation.js` use `x = 101 - x` (known off-by-one between the two conventions)
   - **Opposite Side Logic**: `opp=True` (ball handlers), `opp=False` (outlet players)

**BIP System Flow (6 Steps)**

1. **Made Shot Completes** - Shot animation, celebration, etc. finishes
2. **BIP Turn Created** - Backend creates `BASELINE_INBOUND` turn with player positions
3. **Frontend Routing** - `AnimationEngine.handleBaselineInbound()` routes the turn
4. **Player Positioning** - Players animate to positions based on next turn type (HCO/HCT/FCP)
5. **Inbound Pass Execution** - Inbound pass animation completes (SF → PG)
6. **Next Turn Begins** - HCO/HCT/FCP turn starts with players already in position

**Long Form Documentation**

### Overview

After a made shot (HCO MAKE, PUTBACK_MAKE, Fast Break MAKE, Free Throw MAKE), the next turn is always `BASELINE_INBOUND`. This turn handles player positioning and inbound pass animation before transitioning to the next offensive sequence (HCO, HCT, or FCP).

**Location:** `BackEnd/models/turn_manager.py` - `setup_baseline_inbound()`, `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleBaselineInbound()`  
**Status:** ✅ Fully implemented with FCP/HCT support and pass completion wait logic  
**Scope:** Player positioning and inbound pass execution after made shots

### Process Overview

**Location:** `AnimationEngine.handleBaselineInbound()` → `PassAnimationSystem.executeInboundSequence()` → `runInboundSetup()`

**Flow:**
1. Made shot turn completes (shot animation, celebration, etc.)
2. `BASELINE_INBOUND` turn is created by backend
3. Frontend routes to `AnimationEngine.handleBaselineInbound()`
4. Players are positioned based on next turn type
5. Inbound pass: Executed in `runInboundSetup()` (SF → PG) for **HCO, FCP, and HCT**. FCP/HCT backend trims skeleton to step 1 so clocks start when receiver has the ball.
6. Next turn (HCO/HCT/FCP) begins with players already in position

### Inbound pass and clock start (BIP → FCP/HCT)

**Behavior:** For FCP/HCT, the inbound pass runs during BIP (same as HCO). The frontend runs the full inbound sequence in `runInboundSetup()` — positions plus SF → PG pass — with no early return for FCP/HCT. The backend trims FCP/HCT skeletons to the first post-inbound step when building the next turn (supports step-0-pass and step-1-pass legacy shapes). **Game and shot clocks start when that first post-inbound step runs** (i.e. after the receiver has the ball), matching BIP→HCO and SIP.

**Location:** `turnAnimation.js` `runInboundSetup()` (inbound pass runs for all next-turn types); `BackEnd/engine/phase_resolution.py` `_get_fcp_hct_post_inbound_start_index()` — when the previous turn is BASELINE_INBOUND it dynamically skips **all** leading inbound-equivalent steps (minimum: step 0), so BIP remains the single inbound owner; applied on both FCP/HCT shot and non-shot paths.

**SIP unchanged:** SIP (SIDE_INBOUND) turns use `runSideInboundSetup()`, not `runInboundSetup()`, and always get the full side inbound pass and transition to HCO.

### Three Next Turn Scenarios

#### 1. BASELINE_INBOUND → HCO (Normal Inbound)

**Backend Setup:**
- `turn_manager.py` `setup_baseline_inbound()` with `next_defensive_setup=None`
- Emits explicit `oDestinations` / `dDestinations` for HCO-targeted BIP setup
- **Offense SF (inbound passer):**
  - Home offense: `x = 3`
  - Away offense: `x = 97`
  - Uses current PG `y` plus offense team chemistry to choose `y`:
    - chemistry `> 15`: `y = 25-35` when current PG `y > 24`, else `y = 15-25`
    - chemistry `< 16`: `y = 15-35`
- **Offense PG:**
  - Moves to `y = SF.y +/- 3`
  - Moves `9-15` x-spots toward the offense basket from the SF inbound spot
- **Other three offensive players:**
  - Random destinations within `+/- 20` y-spots of the offense basket y
  - `5-25` x-spots from the offense basket x
- **Defense:**
  - If `defense_execution > 5`: all 5 defenders target lane locations
  - Else if `defense_execution > 0`: 4 defenders target lane locations
  - Else: 2 defenders target lane locations
  - Lane location range:
    - `y = 19-32`
    - Home offense: `x = 74-87`
    - Away offense: flipped to away-side coordinates
  - Non-lane defenders:
    - `y = 10-30`
    - Home offense: `x = 62-87`
    - Away offense: flipped to away-side coordinates

**Frontend Execution:**
- `runInboundSetup()` called with `skipRetreat=false`
- **Defensive players:** Animate to backend `dDestinations`
- **Offensive players:** Animate to backend `oDestinations`
- **BIP setup advance trigger:** SF and PG both reaching their setup destinations
- **Boundary behavior at trigger:** all other setup movers are force-stopped at their live positions and the phase proceeds from that live state
- **Inbound pass progression:**
  - The ball remains at its live made-shot resolution spot
  - SF first moves to that ball spot
  - When SF reaches the ball spot, the ball attaches to the SF sprite
  - SF then carries the ball to the inbound setup destination
  - PG and the other setup movers reach their setup destinations in parallel
  - Ball is passed from SF → PG
  - Trigger event is the ball attaching to the PG sprite on pass receipt
  - No extra post-pass hold is applied after PG receives the inbound; BIP hands off immediately toward HCO bring-up / setup continuation once the pass is complete

**Key Code:**
- `BackEnd/models/turn_manager.py` `setup_baseline_inbound()`: HCO-targeted `oDestinations` / `dDestinations`
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` `runInboundSetup()`: BIP setup tweening and inbound pass sequencing

#### 2. BASELINE_INBOUND → HCT (Half Court Trap)

**Backend Setup (Dynamic HCT — bypasses the MongoDB skeleton):**
- `turn_manager.py` `setup_baseline_inbound()` with `next_defensive_setup="HCT"`
- **Offense:** static `HCT_SETUP_POSITIONS` mapping → `HCO_STRING_SPOTS` coords (flipped for away offense). `offense_setup_positions` is built directly from those computed `o_dest` coords — **not** from a skeleton step 0 (pulling skeleton step 0 would override authored spots and cause BH hold drift; see `Dynamic_HCT_Turns.md`)
- **Defense:** `hct_initial_defender_coords(is_away_offense)` from `BackEnd/engine/dynamic_hct.py` — PG at center court (`DEFENSIVE_PG_STEP_1_TARGET`), the other four at the **centroid of their `HCT_STANDARD_NORMAL` polygon**, so BIP-end matches dynamic HCT step 0 with no teleport
- SF is the inbounder (uses `inbound_left` location from `HCT_SETUP_POSITIONS`)

**Frontend Execution:**
- `runInboundSetup()` called with `skipRetreat=true`, `pressureType="HCT"`
- **Defensive players:** Animate directly to the backend `dDestinations` (HCT initial alignment above; no retreat)
- **Offensive players:** Animate to skeleton step 0 positions from `offense_setup_positions`
  - **Critical:** Frontend checks `coords` field first (has `opp` logic applied)
  - Falls back to `location` field if `coords` missing
  - Applies `opp` logic when using `location`:
    - `opp=True`: Flip coords for home offense (ball handlers go to away side)
    - `opp=False`: Flip coords for away offense (outlet players go to away side)
- **Inbound pass:** SF → PG **is** animated in `runInboundSetup()` for HCT (same as HCO). HCT turn animation starts at step 1; clocks start when the receiver has the ball (see **Inbound pass and clock start** above).
- **HCT Turn Start:** ✅ **NEW** (January 2025) - `playTurnAnimation()` skips `runSetupTween()` when `fromInbound === true` AND `isFCPHCT === true`
  - Players are already positioned at step 0 from BIP, so redundant positioning is skipped
  - Prevents timing conflicts with inbound pass animation completion
- **BIP Pass Completion Wait:** ✅ **NEW** (January 2025) - `handleBaselineInbound()` explicitly waits for inbound pass animation to fully complete before returning
  - **Problem Fixed:** HCT/FCP turn was starting before BIP pass animation finished, causing sequencing bug where HCT setup step ran, then BIP pass executed, then HCT continued
  - **Solution:** After `executeInboundSequence()` completes, checks `scene.passInFlight` flag and waits for it to clear
  - **Implementation:** Listens for `passEnd` event and polls `passInFlight` as fallback, with a short bounded safety timeout (600ms) to prevent long turn-boundary stalls
  - **Location:** `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleBaselineInbound()` (search `PASS_COMPLETION_MAX_WAIT_MS`)
  - **Why It Matters:** Ensures BIP animation fully completes before next turn (HCT/FCP) starts, preventing visual glitches and timing conflicts

**Key Code:**
- `BackEnd/engine/dynamic_hct.py` `hct_initial_defender_coords()`: HCT defensive BIP-end alignment
- `turnAnimation.js`: skip `runSetupTween()` when `fromInbound && isFCPHCT`
- `AnimationEngine.js` `handleBaselineInbound()`: BIP pass completion wait logic

#### 3. BASELINE_INBOUND → FCP (Full Court Press)

**Backend Setup (randomized — replaces the legacy skeleton-step-0 / static-positions approach):**
- `turn_manager.py` `setup_baseline_inbound()` with `next_defensive_setup="FCP"`
- **Offense + defense generated together** by `_build_fcp_setup_positions()`:
  - Offense per-position ranges from `FCP_OFFENSE_SETUP_RANGES` (PG/SG/PF/C); **SF** uses the same chemistry-aware dynamic-y logic as HCO BIP (sf_x = baseline inbound x; sf_y range biased by team chemistry + current PG y)
  - Defense per-position ranges from `FCP_DEFENSE_SETUP_RANGES` (all 5 — replaces the legacy `get_defender_coords`-derived layout for FCP)
  - **Collision resolution:** any exact (x, y) pair collision is broken by moving one random player `FCP_SETUP_COLLISION_OFFSET_GRID` spots in a random direction, re-checked ≤10 rounds
  - Generated in home orientation; flipped via `getAwayTeamCoords` for away offense
  - Full details: `FCP_HCT_System.md` → "FCP Starting Alignment"
- `offense_setup_positions` is built from those `o_dest` coords — **not** from skeleton step 0. Players animate from BIP-end coords toward the first post-inbound skeleton step at archetype rate (non-gate movers freeze at the interrupted coord per UESS §9.5 — no teleport)
- SF is the inbounder (baseline inbound spot)
- (`get_skeleton_for_turn` step-0 sourcing remains only as the fallback for hypothetical future pressure types — neither HCT nor FCP uses it)

**Frontend Execution:**
- `runInboundSetup()` called with `skipRetreat=true`, `pressureType="FCP"`
- **Defensive players:** Animate directly to the backend `dDestinations` (randomized FCP alignment above; no retreat)
- **Offensive players:** Animate to `offense_setup_positions` coords
  - Frontend checks `coords` field first; falls back to `location` field with manual `opp` application (legacy shapes only)
- **Inbound pass:** SF → PG **is** animated in `runInboundSetup()` for FCP (same as HCO). FCP turn animation starts at step 1; clocks start when the receiver has the ball (see **Inbound pass and clock start** above).
- **FCP Turn Start:** ✅ **NEW** (January 2025) - `playTurnAnimation()` skips `runSetupTween()` when `fromInbound === true` AND `isFCPHCT === true`
  - Players are already positioned at step 0 from BIP, so redundant positioning is skipped
  - Prevents timing conflicts with inbound pass animation completion
- **BIP Pass Completion Wait:** ✅ **NEW** (January 2025) - `handleBaselineInbound()` explicitly waits for inbound pass animation to fully complete before returning
  - **Problem Fixed:** HCT/FCP turn was starting before BIP pass animation finished, causing sequencing bug where HCT setup step ran, then BIP pass executed, then HCT continued
  - **Solution:** After `executeInboundSequence()` completes, checks `scene.passInFlight` flag and waits for it to clear
  - **Implementation:** Listens for `passEnd` event and polls `passInFlight` as fallback, with a short bounded safety timeout (600ms) to prevent long turn-boundary stalls
  - **Location:** `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleBaselineInbound()` (search `PASS_COMPLETION_MAX_WAIT_MS`)
  - **Why It Matters:** Ensures BIP animation fully completes before next turn (HCT/FCP) starts, preventing visual glitches and timing conflicts

**Key Code:**
- `BackEnd/models/turn_manager.py` `_build_fcp_setup_positions()`: randomized FCP offense + defense BIP-end alignment
- `BackEnd/constants.py` `FCP_OFFENSE_SETUP_RANGES` / `FCP_DEFENSE_SETUP_RANGES` / `FCP_SETUP_COLLISION_OFFSET_GRID`
- `turnAnimation.js`: skip `runSetupTween()` when `fromInbound && isFCPHCT`
- `AnimationEngine.js` `handleBaselineInbound()`: BIP pass completion wait logic

**Important Notes:**
- FCP positions are more aggressive (deeper in offensive zone)
- Inbound spot: home offense at left baseline (x=3); away offense flipped to right baseline via coordinate flipping

### Quarter Start BASELINE_INBOUND Turns

**Possession Pattern:**
- **Q1:** Opening Tip (not BIP)
- **Q2:** Team that did NOT win opening tip gets possession
- **Q3:** Team that did NOT win opening tip gets possession (same as Q2)
- **Q4:** Opening tip winner gets possession
- **Overtime:** Opening Tip (not BIP) - every OT quarter starts with opening tip

**Storage:**
- Opening tip winner stored in `game_state["opening_tip_winner"]` as `"home"` or `"away"`
- Set by: `BackEnd/utils/opening_tip.py` `execute_opening_tip()`
- Used by: `BackEnd/main.py` `simulate_quarter()` for Q2/Q3/Q4 possession determination

**Backend Implementation (`BackEnd/main.py`):**

For Q2, Q3, and Q4:
1. Determine possession based on `opening_tip_winner` from game state
2. Set offense/defense teams
3. Check for defensive pressure (FCP/HCT)
4. Create BASELINE_INBOUND turn using `turn_manager.setup_baseline_inbound()`
5. Add turn metadata (`text`, `time_elapsed`, `possession_flips`, `quarter`)
6. Append to `game.turns` array

**Frontend Handling:**
- Quarter start BIPs use the exact same code path as post-shot BIPs
- Same routing: `AnimationEngine.handleBaselineInbound()`
- Same execution: `PassAnimationSystem.executeInboundSequence()` → `runInboundSetup()`
- Same player positioning logic (HCO/HCT/FCP based on `next_defensive_setup`)
- No special handling required - unified system

**Key Benefits:**
- Unified system for all BASELINE_INBOUND turns (post-shot and quarter start)
- Consistent frontend handling - no special-case code
- Supports defensive pressure (FCP/HCT) at quarter starts
- Follows standard basketball possession rules (alternating pattern)

**Key Files:**
- `BackEnd/main.py`: Quarter start logic (Q2/Q3/Q4 BASELINE_INBOUND branches in `simulate_quarter()`)
- `BackEnd/utils/opening_tip.py`: Opening tip execution and winner storage
- `BackEnd/models/turn_manager.py` `setup_baseline_inbound()`: BASELINE_INBOUND turn creation

### Coordinate System and `opp` Field

**Home Orientation:**
- `HCO_STRING_SPOTS` coordinates are in home team orientation
- Home team attacks right basket (x=91), away team attacks left basket (x=9)
- Midcourt is x=50

**Opposite Side Logic (`opp` field) — legacy:** no longer part of the BIP→HCT/FCP setup path (HCT uses authored `HCT_SETUP_POSITIONS` coords; FCP uses randomized ranges; both ship pre-computed `coords`). The `opp` machinery below applies only to legacy skeleton shapes that still carry `location` + `opp` fields.
- **Purpose:** Determines which offensive players go to opposite side (defensive side) during press break
- **`opp=True`:** Ball handlers (usually PG) - go to opposite side to break press
- **`opp=False`:** Outlet players (SG, SF, PF, C) - stay on normal offense side
- **Backend:** `apply_opposite_side_logic()` converts locations to coords and stores in `coords` field
- **Frontend:** Prioritizes `coords` field (backend-applied logic), falls back to `location` with manual `opp` application

**Coordinate Flipping:**
- Backend formula: `x = 100 - x` (`getAwayTeamCoords` in `shared.py`); legacy frontend helpers use `x = 101 - x`
- Applied for:
  - Away team offense (normal flip)
  - Home team offense with `opp=True` (ball handlers go to away side)
  - Away team offense with `opp=False` (outlet players go to away side)

### Key Functions

**Backend:**
- `turn_manager.py` `setup_baseline_inbound()`: Creates BASELINE_INBOUND turn data (includes `turn_type` + `current_turn` markers, position snapshot, and unified `animation_steps[]`)
- `turn_manager.py` `_build_fcp_setup_positions()`: Randomized FCP BIP-end alignment (offense + defense)
- `dynamic_hct.py` `hct_initial_defender_coords()`: HCT defensive BIP-end alignment
- `transition_bridge.py` `build_bip_animation_steps()`: 2-step unified BIP schema
- `phase_resolution.py` `get_skeleton_for_turn()` / `apply_opposite_side_logic()`: **legacy** — used only as the fallback for future pressure types; neither HCT nor FCP sources BIP setup from skeletons anymore

**Frontend:**
- `AnimationEngine.handleBaselineInbound()`: Routes BASELINE_INBOUND turns
- `PassAnimationSystem.executeInboundSequence()`: Handles inbound pass execution
- `turnAnimation.js` `runInboundSetup()`: Positions players and executes inbound pass

### Key Files

**Backend:**
- `BackEnd/models/turn_manager.py` - `setup_baseline_inbound()`, `_build_fcp_setup_positions()`
- `BackEnd/engine/dynamic_hct.py` - `hct_initial_defender_coords()`
- `BackEnd/utils/transition_bridge.py` - `build_bip_animation_steps()`
- `BackEnd/main.py` - Quarter start logic (Q2/Q3/Q4 BASELINE_INBOUND)
- `BackEnd/utils/opening_tip.py` - Opening tip execution and winner storage
- `BackEnd/engine/phase_resolution.py` - `get_skeleton_for_turn()`, `apply_opposite_side_logic()` (legacy fallback only)

**Frontend:**
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleBaselineInbound()` method
- `FrontEnd/static/js/phaser/animation/PassAnimationSystem.js` - `executeInboundSequence()` method
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `runInboundSetup()` function (incl. FCP/HCT `runSetupTween` skip)
- `FrontEnd/static/js/phaser/animation/animationPlayback.js` - schema playback for unified BIP `animation_steps[]`
