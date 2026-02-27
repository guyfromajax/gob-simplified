## BASELINE_INBOUND (BIP) System ✅ **COMPLETE** (January 2025)

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
   - **Coordinate Flipping Formula**: `x = 101 - x` (flips around midcourt)
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

**Behavior:** For FCP/HCT, the inbound pass runs during BIP (same as HCO). The frontend runs the full inbound sequence in `runInboundSetup()` — positions plus SF → PG pass — with no early return for FCP/HCT. The backend trims the FCP/HCT skeleton to start at step 1 when building the turn, so the first animated step is post-receive. **Game and shot clocks start when that first step runs** (i.e. after the receiver has the ball), matching BIP→HCO and SIP.

**Location:** `turnAnimation.js` `runInboundSetup()` (inbound pass runs for all next-turn types); `BackEnd/engine/phase_resolution.py` (skeleton trimmed to `steps[1:]` for FCP/HCT shot and non-shot paths).

**SIP unchanged:** SIP (SIDE_INBOUND) turns use `runSideInboundSetup()`, not `runInboundSetup()`, and always get the full side inbound pass and transition to HCO.

### Three Next Turn Scenarios

#### 1. BASELINE_INBOUND → HCO (Normal Inbound)

**Backend Setup:**
- `turn_manager.py` `setup_baseline_inbound()` with `next_defensive_setup=None`
- Creates random baseline positions for offensive players (PG, SG, SF, PF, C)
- PG is the inbounder (stays at inbound spot)
- Defensive players retreat to midcourt

**Frontend Execution:**
- `runInboundSetup()` called with `skipRetreat=false`
- **Defensive players:** Animate to midcourt (x: 45 or 55) - retreat animation
- **Offensive players:** Animate to random baseline positions from `oDestinations`
- **Inbound pass:** SF → PG (hardcoded fallback, or dynamic from `turnData.animations`)

**Key Code:**
- `turnAnimation.js` lines 1031-1078: Defensive retreat animation
- `turnAnimation.js` lines 1220-1224: Offensive player positioning (uses `inboundDest`)

#### 2. BASELINE_INBOUND → HCT (Half Court Trap)

**Backend Setup:**
- `turn_manager.py` `setup_baseline_inbound()` with `next_defensive_setup="HCT"`
- Retrieves HCT skeleton step 0 via `get_skeleton_for_turn("HCO", "HCT", game)`
- Extracts `pos_actions` from step 0 and includes in `offense_setup_positions`
- Applies `apply_opposite_side_logic()` to skeleton (handles `opp` field)
- SF is the inbounder (uses `inbound_left` location from `HCT_SETUP_POSITIONS`)

**Frontend Execution:**
- `runInboundSetup()` called with `skipRetreat=true`, `pressureType="HCT"`
- **Defensive players:** Animate directly to HCT trap positions (no retreat)
  - Positions: PG at x=60, SG/SF at x=55, PF/C at x=45 (home orientation)
  - Flipped for away team defense
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
  - **Implementation:** Listens for `passEnd` event and polls `passInFlight` as fallback, with 2-second safety timeout
  - **Location:** `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleBaselineInbound()` function (lines 354-395)
  - **Why It Matters:** Ensures BIP animation fully completes before next turn (HCT/FCP) starts, preventing visual glitches and timing conflicts

**Key Code:**
- `turnAnimation.js` lines 1186-1225: Skeleton position conversion with `opp` logic
- `turnAnimation.js` lines 1079-1128: HCT defensive positioning
- `BackEnd/engine/phase_resolution.py` `apply_opposite_side_logic()`: Backend `opp` handling
- `turnAnimation.js` lines 2211-2217: Skip `runSetupTween()` for BIP → HCT transitions
- `AnimationEngine.js` lines 354-395: BIP pass completion wait logic

**Important Notes:**
- `opp` field determines which players go to opposite side (defensive side)
- Ball handlers (usually PG) have `opp=True` and go to opposite side
- Outlet players have `opp=False` and stay on normal offense side
- Coordinate flipping formula: `x = 101 - x` for away team offense

#### 3. BASELINE_INBOUND → FCP (Full Court Press)

**Backend Setup:**
- `turn_manager.py` `setup_baseline_inbound()` with `next_defensive_setup="FCP"`
- Retrieves FCP skeleton step 0 via `get_skeleton_for_turn("HCO", "FCP", game)`
- Extracts `pos_actions` from step 0 and includes in `offense_setup_positions`
- Applies `apply_opposite_side_logic()` to skeleton (handles `opp` field)
- SF is the inbounder (uses `inbound_left` location from `FCP_SETUP_POSITIONS`)

**Frontend Execution:**
- `runInboundSetup()` called with `skipRetreat=true`, `pressureType="FCP"`
- **Defensive players:** Animate directly to FCP press positions (no retreat)
  - Positions: PG at x=80, SG/SF at x=73, PF/C at x=37/35 (home orientation)
  - Flipped for away team defense
- **Offensive players:** Animate to skeleton step 0 positions from `offense_setup_positions`
  - **Critical:** Frontend checks `coords` field first (has `opp` logic applied)
  - Falls back to `location` field if `coords` missing
  - Applies `opp` logic when using `location` (same as HCT)
- **Inbound pass:** SF → PG **is** animated in `runInboundSetup()` for FCP (same as HCO). FCP turn animation starts at step 1; clocks start when the receiver has the ball (see **Inbound pass and clock start** above).
- **FCP Turn Start:** ✅ **NEW** (January 2025) - `playTurnAnimation()` skips `runSetupTween()` when `fromInbound === true` AND `isFCPHCT === true`
  - Players are already positioned at step 0 from BIP, so redundant positioning is skipped
  - Prevents timing conflicts with inbound pass animation completion
- **BIP Pass Completion Wait:** ✅ **NEW** (January 2025) - `handleBaselineInbound()` explicitly waits for inbound pass animation to fully complete before returning
  - **Problem Fixed:** HCT/FCP turn was starting before BIP pass animation finished, causing sequencing bug where HCT setup step ran, then BIP pass executed, then HCT continued
  - **Solution:** After `executeInboundSequence()` completes, checks `scene.passInFlight` flag and waits for it to clear
  - **Implementation:** Listens for `passEnd` event and polls `passInFlight` as fallback, with 2-second safety timeout
  - **Location:** `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleBaselineInbound()` function (lines 354-395)
  - **Why It Matters:** Ensures BIP animation fully completes before next turn (HCT/FCP) starts, preventing visual glitches and timing conflicts

**Key Code:**
- `turnAnimation.js` lines 1186-1225: Skeleton position conversion with `opp` logic
- `turnAnimation.js` lines 1079-1128: FCP defensive positioning
- `BackEnd/engine/phase_resolution.py` `apply_opposite_side_logic()`: Backend `opp` handling
- `turnAnimation.js` lines 2211-2217: Skip `runSetupTween()` for BIP → FCP transitions
- `AnimationEngine.js` lines 354-395: BIP pass completion wait logic

**Important Notes:**
- Same `opp` logic as HCT (ball handlers vs outlet players)
- FCP positions are more aggressive (deeper in offensive zone)
- `inbound_left` vs `inbound_right` determined by offense team:
  - Home offense: Uses `inbound_left` (x=3) - correct
  - Away offense: Backend flips to `inbound_right` (x=97) via coordinate flipping

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
- `BackEnd/main.py` lines 328-453: Quarter start logic (Q2/Q3/Q4 BASELINE_INBOUND)
- `BackEnd/utils/opening_tip.py`: Opening tip execution and winner storage
- `BackEnd/models/turn_manager.py` `setup_baseline_inbound()`: BASELINE_INBOUND turn creation

### Coordinate System and `opp` Field

**Home Orientation:**
- `HCO_STRING_SPOTS` coordinates are in home team orientation
- Home team attacks right basket (x=91), away team attacks left basket (x=9)
- Midcourt is x=50

**Opposite Side Logic (`opp` field):**
- **Purpose:** Determines which offensive players go to opposite side (defensive side) during press break
- **`opp=True`:** Ball handlers (usually PG) - go to opposite side to break press
- **`opp=False`:** Outlet players (SG, SF, PF, C) - stay on normal offense side
- **Backend:** `apply_opposite_side_logic()` converts locations to coords and stores in `coords` field
- **Frontend:** Prioritizes `coords` field (backend-applied logic), falls back to `location` with manual `opp` application

**Coordinate Flipping:**
- Formula: `x = 101 - x` (flips around midcourt)
- Applied for:
  - Away team offense (normal flip)
  - Home team offense with `opp=True` (ball handlers go to away side)
  - Away team offense with `opp=False` (outlet players go to away side)

### Key Functions

**Backend:**
- `turn_manager.py` `setup_baseline_inbound()`: Creates BASELINE_INBOUND turn data
- `phase_resolution.py` `get_skeleton_for_turn()`: Retrieves FCP/HCT skeleton
- `phase_resolution.py` `apply_opposite_side_logic()`: Applies `opp` field logic

**Frontend:**
- `AnimationEngine.handleBaselineInbound()`: Routes BASELINE_INBOUND turns
- `PassAnimationSystem.executeInboundSequence()`: Handles inbound pass execution
- `turnAnimation.js` `runInboundSetup()`: Positions players and executes inbound pass

### Key Files

**Backend:**
- `BackEnd/models/turn_manager.py` - `setup_baseline_inbound()` method (lines 140-258)
- `BackEnd/main.py` - Quarter start logic (Q2/Q3/Q4 BASELINE_INBOUND, lines 328-453)
- `BackEnd/utils/opening_tip.py` - Opening tip execution and winner storage
- `BackEnd/engine/phase_resolution.py` - `get_skeleton_for_turn()`, `apply_opposite_side_logic()`

**Frontend:**
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleBaselineInbound()` method (lines 309-395)
- `FrontEnd/static/js/phaser/animation/PassAnimationSystem.js` - `executeInboundSequence()` method
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `runInboundSetup()` function (lines 1031-1225, FCP/HCT skip ~1849-1866)

