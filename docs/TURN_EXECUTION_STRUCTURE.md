# Turn Execution Structure Analysis

This document maps the execution structure of each turn type to identify patterns, streamline code, and ensure all execution cases are handled.

## Turn Type Execution Patterns

### 1. HCO (Half Court Offense)

**Structure**: `Skeleton Animation + Result Handling`

**Execution Flow**:
1. **Setup**: Players move to step 0 positions (from previous turn or inbound)
2. **Skeleton Animation**: Animate all steps from playcall skeleton (full skeleton, tempo doesn't affect step count anymore)
3. **Result Handling**:
   - **MAKE**: Ball hold at rim → Inbound pass (if no foul) OR Free throw (if foul/AND-1)
   - **MISS**: Rebound handling (OREB or DREB)
   - **FOUL**: Foul animation → Free throw (if shooting/bonus) OR Side inbound (if non-shooting, no bonus)
   - **TURNOVER**: Turnover animation → Side inbound (PC) OR Fast Break (if live ball)
   - **STEAL**: Steal animation → HCO (PC) OR Fast Break (PC)

**Key Characteristics**:
- Full skeleton animation (all steps from playcall)
- Result determined AFTER skeleton completes
- Result handling is separate from skeleton animation

**Code Locations**:
- Backend: `resolve_half_court_offense_logic()` → `shot_manager.resolve_shot()`
- Frontend: `AnimationRouter` → `ShotAnimationSystem.processShot()` → `playTurnAnimation()`

---

### 2. FCP / HCT (Full Court Press / Half Court Trap)

**Structure**: `Skeleton Animation + Result Handling` (Same as HCO)

**Execution Flow**:
1. **Setup**: Players move to step 0 positions (from inbound or previous pressure turn)
2. **Skeleton Animation**: Animate all skeleton steps (full skeleton, same as HCO)
   - Uses press break skeletons (different data from playcall skeletons, but same animation system)
   - Full skeleton animation (all steps) - same pattern as HCO
3. **Result Handling**: 
   - **Unique Results**: Press Break/Trap Break to HCO (unique to FCP/HCT)
   - **Common Results**: MAKE, MISS, STEAL, DEAD_BALL_TURNOVER, FOUL, TURNOVER
   - Same result handling pattern as HCO (routed through same handlers)

**Key Characteristics**:
- ✅ **Uses same execution pattern as HCO** - Routes through AnimationRouter
- ✅ Full skeleton animation (all steps) - same as HCO
- ✅ Uses press break skeletons (different data, but same animation system)
- ✅ Routes to SHOT_ATTEMPT handler (for MAKE/MISS) or respective handlers (FOUL, TURNOVER, etc.)
- ✅ No special routing needed - unified with HCO system

**Code Locations**:
- Backend: `resolve_full_court_press_logic()` / `resolve_half_court_trap_logic()` → Press break skeleton data
- Frontend: `AnimationRouter` → Routes to same handlers as HCO (SHOT_ATTEMPT, FOUL, TURNOVER, etc.)
- Frontend: `playTurnAnimation()` → Same skeleton animation system as HCO

**Similarities to HCO**:
- ✅ Full skeleton animation (all steps)
- ✅ Routes through AnimationRouter
- ✅ Same result handling pattern
- ✅ Same animation system (`playTurnAnimation()`)
- ✅ Only difference: Uses press break skeleton data (not playcall skeleton data)

**State Management**:
- FCP/HCT state set via `next_defensive_setup` on BASELINE_INBOUND turns
- `scene.currentPressureType` tracks active pressure type ("FCP" or "HCT")
- `scene.pressureSequenceActive` tracks if pressure sequence is active
- State cleared when sequence completes (shot attempt completes, foul, turnover, or transition to HCO)

---

### 3. Free Throw

**Structure**: `Setup Animation + Result Handling`

**Execution Flow**:
1. **Setup Animation**: 
   - Players move to free throw line positions (offense + defense)
   - Ball attaches to shooter
   - Lane setup (or no-lane for technical fouls)
2. **Shot Animation**: Ball flight to rim
3. **Result Handling**:
   - **MAKE**: Ball hold at rim → Next free throw (if more remain) OR Inbound pass (if final)
   - **MISS**: Ball bounce from rim → Rebound handling (OREB or DREB)

**Bonus vs Set Number Handling**:
- **Turn-by-Turn Mode** (Preferred):
  - Uses `free_throws_remaining` field (number of FTs remaining after this turn)
  - If `free_throws_remaining > 0`: More shots remain
  - If `free_throws_remaining === 0`: This was the final shot
  - Works for all bonus types (1-and-1, 2-shot, 3-shot) and set number FTs
- **Batch Mode** (Fallback):
  - Uses `ftContext` (ftIndex, ftTotal, bonusType) if `free_throws_remaining` is undefined
  - **1-and-1 Bonus**: 
    - First shot: If made → Second shot (ftIndex: 1, ftTotal: 2)
    - If missed → Rebound
    - Second shot: If made → Inbound pass, If missed → Rebound
  - **2-Shot Bonus**: 
    - First shot: If made → Second shot (ftIndex: 1, ftTotal: 2)
    - Second shot: If made → Inbound pass, If missed → Rebound
  - **3-Shot Bonus**: 
    - First shot: If made → Second shot (ftIndex: 1, ftTotal: 3)
    - Second shot: If made → Third shot (ftIndex: 2, ftTotal: 3)
    - Third shot: If made → Inbound pass, If missed → Rebound
  - **Set Number (Non-Bonus)**: 
    - Each shot: If made → Next shot (if more remain) OR Inbound pass (if final)
    - If missed → Rebound

**Key Characteristics**:
- Setup is always the same (FT line positions)
- Result handling varies by bonus type and remaining shots
- **Turn-by-turn mode**: Uses `free_throws_remaining` to determine if more shots remain (preferred)
- **Batch mode**: Uses `ftContext` (ftIndex, ftTotal) if `free_throws_remaining` is undefined (fallback)

**Code Locations**:
- Backend: `resolve_free_throw_logic()` → `capture_free_throw_animation()`
- Frontend: `FreeThrowAnimationSystem.processFreeThrow()` → `executeFreeThrowSequence()`

---

### 4. BIP (Baseline Inbound Pass)

**Structure**: `Standard Animation + FCP/HCT Setup (Conditional)`

**Execution Flow**:
1. **Setup Animation**: 
   - Offense: Players move to baseline inbound positions
   - Defense: Players move to defensive positions (normal OR FCP/HCT if `next_defensive_setup`)
2. **Pass Animation**: Inbound pass (SF → PG, or dynamic from animation data)
3. **State Setup**: 
   - If `next_defensive_setup === "FCP"` or `"HCT"`: Set `pressureSequenceActive = true`
   - Otherwise: Normal inbound (no pressure state)

**Key Characteristics**:
- Standard animation (positioning + pass)
- **Special handling**: Must check `next_defensive_setup` to set FCP/HCT state
- Sets up the NEXT turn (FCP/HCT or HCO)

**Code Locations**:
- Backend: `setup_baseline_inbound()` → `get_defender_coords()` (with pressure type)
- Frontend: `AnimationEngine.handleBaselineInbound()` → `runInboundSetup()`

---

### 5. SIP (Side Inbound Pass)

**Structure**: `Standard Animation`

**Execution Flow**:
1. **Setup Animation**: 
   - Offense: Players move to sideline inbound positions
   - Defense: Players move to defensive positions (normal, no FCP/HCT)
2. **Pass Animation**: Inbound pass (dynamic from animation data or fallback)
3. **State Setup**: Always transitions to HCO (no pressure setup)

**Key Characteristics**:
- Standard animation (positioning + pass)
- No FCP/HCT setup (only BIP handles pressure)
- Always leads to HCO

**Code Locations**:
- Backend: `setup_side_inbound()`
- Frontend: `AnimationEngine.handleSideInbound()` → `runInboundSetup()`

---

### 6. Fast Break

**Structure**: `Outlet Pass (Conditional) + Fast Break Resolution`

**Execution Flow**:
1. **Phase 1: Outlet Pass (Conditional)**:
   - **If DREB-initiated**: Outlet pass from rebounder to outlet receiver
   - **If STEAL-initiated**: No outlet pass (ball already with stealer)
2. **Phase 2: Fast Break Resolution**:
   - Animate fast break sequence (players moving down court)
   - Resolve outcome:
     - **MAKE**: Shot animation → Inbound pass (if no foul) OR Free throw (if foul)
     - **MISS**: Shot animation → Rebound handling (OREB or DREB)
     - **DEFENSIVE_STOP**: Fast break stopped → HCO (no possession change) - **Unique to Fast Break**
     - **FOUL**: Foul animation → Free throw (if shooting/bonus) OR Side inbound (if non-shooting)
     - **TURNOVER**: Turnover animation → Side inbound (PC) OR Fast Break (PC, if live ball)

**Key Characteristics**:
- Two-phase structure (outlet pass + resolution)
- Outlet pass is conditional (only for DREB-initiated)
- Fast break resolution is similar to HCO shot resolution
- Uses `fast_break` flag and `roles` (outlet_passer, outlet_receiver)
- **Unique Result**: DEFENSIVE_STOP (not available in HCO, FCP, HCT)

**Code Locations**:
- Backend: `resolve_fast_break_logic()` → `capture_fast_break_animation()`
- Frontend: `AnimationEngine.handleFastBreak()` → `runFastBreakSequence()`

---

### 7. OREB (Offensive Rebound)

**Structure**: `Rebound Animation + Putback/Kickout Decision`

**Execution Flow**:
1. **Rebound Animation**: 
   - Ball bounces from rim to rebounder
   - Rebounder catches ball
2. **Decision Point**: Putback attempt OR Kickout pass
   - **Putback Attempt**: 
     - Rebounder shoots immediately (PUTBACK_MAKE or PUTBACK_MISS)
     - If PUTBACK_MAKE: Inbound pass (if no foul) OR Free throw (if foul)
     - If PUTBACK_MISS: Another OREB (if offensive rebound) OR DREB (if defensive rebound)
   - **Kickout Pass**: 
     - Rebounder passes to perimeter → HCO (no possession change)

**Key Characteristics**:
- Rebound animation is always the same
- Decision (putback vs kickout) happens after rebound
- Putback attempts create separate PUTBACK_MAKE/PUTBACK_MISS turns
- Consecutive OREBs are batched in same API call

**Code Locations**:
- Backend: `resolve_offensive_rebound_turn()` → `resolve_putback_attempt()` or `resolve_kickout_pass()`
- Frontend: `handleOrebTurn()` → Putback animation OR Kickout animation

---

### 8. Opening Tip

**Structure**: `Standard Animation + Result Resolution`

**Execution Flow**:
1. **Setup Animation**: 
   - Both teams' centers at center court
   - Ball at center court
2. **Tip Animation**: Ball goes up, both centers jump
3. **Result Resolution**: 
   - Winner gains possession
   - Transitions to HCO (winning team on offense)

**Key Characteristics**:
- Simple animation (tip + possession determination)
- Always leads to HCO
- Only occurs at start of Q1 or OT

**Code Locations**:
- Backend: `resolve_opening_tip()` (if exists) or handled in `simulate_quarter()`
- Frontend: `AnimationEngine.handleOpeningTip()` or `playTurnAnimation()`

---

## Missing Turn Types?

Based on `transition_registry.py`, all turn types are:
- ✅ OPENING_TIP
- ✅ INBOUND_PASS (BIP)
- ✅ SIDE_INBOUND_PASS (SIP)
- ✅ HCO
- ✅ OREB
- ✅ FREE_THROW
- ✅ FAST_BREAK
- ✅ FCP
- ✅ HCT

**All turn types are accounted for.**

---

## Code Reuse Opportunities

### 1. **Skeleton Animation System**
- **Shared by**: HCO, FCP, HCT
- **Unified**: All use full skeleton animation (all steps)
  - HCO: Uses playcall skeletons
  - FCP/HCT: Uses press break skeletons (different data, same animation system)
- **Status**: ✅ **Unified** - All use `playTurnAnimation()` with full skeleton animation

### 2. **Result Handling**
- **Shared by**: HCO, FCP, HCT, Fast Break, OREB Putback
- **Common Results**: MAKE, MISS, FOUL, TURNOVER, STEAL
- **Unique Results**:
  - FCP/HCT: Press Break/Trap Break to HCO
  - Fast Break: DEFENSIVE_STOP
  - OREB Putback: PUTBACK_MAKE, PUTBACK_MISS
- **Streamlining**: Unified result handler with turn-type-specific logic (but results are NOT identical)

### 3. **Inbound Pass System**
- **Shared by**: BIP, SIP
- **Differences**: 
  - BIP: Handles FCP/HCT setup
  - SIP: Always leads to HCO
- **Streamlining**: Unified inbound system with conditional pressure setup

### 4. **Rebound System**
- **Shared by**: HCO MISS, Free Throw MISS, Fast Break MISS, OREB Putback MISS
- **Common Logic**: Ball bounce → Rebounder catch → Decision (OREB vs DREB)
- **Streamlining**: Already unified in `ReboundAnimationSystem`

### 5. **Setup Tween (Step 0 Positioning)**
- **Shared by**: HCO, FCP, HCT, Fast Break (after outlet)
- **Common Logic**: Move players to step 0 positions before skeleton animation
- **Streamlining**: Already unified in `runSetupTween()`

---

## Execution Case Coverage

### HCO Execution Cases:
- ✅ MAKE (no foul) → Inbound pass
- ✅ MAKE (foul) → Free throw
- ✅ MISS (OREB) → OREB turn
- ✅ MISS (DREB) → HCO (PC) OR Fast Break (PC)
- ✅ FOUL (shooting) → Free throw
- ✅ FOUL (non-shooting, bonus) → Free throw
- ✅ FOUL (non-shooting, no bonus) → Side inbound
- ✅ TURNOVER (dead ball) → Side inbound (PC)
- ✅ TURNOVER (live ball) → Fast Break (PC)
- ✅ STEAL → HCO (PC) OR Fast Break (PC)
- ⚠️ **Future**: More result types (fouls, turnovers) - structure supports this

### FCP/HCT Execution Cases:
- ✅ MAKE/MISS → Routes to SHOT_ATTEMPT handler (same as HCO)
- ✅ HCO (press break) → HCO (no PC)
- ✅ FOUL → Routes to FOUL handler (same as HCO)
- ✅ TURNOVER → Routes to TURNOVER handler (same as HCO)
- ✅ STEAL → Routes to STEAL handler (same as HCO)
- ✅ DEAD BALL → Routes to DEAD_BALL handler (same as HCO)
- ✅ **Fixed**: Now routes through AnimationRouter (same as HCO) - no special routing needed

### Free Throw Execution Cases:
- ✅ **Turn-by-turn mode**: Uses `free_throws_remaining` field
  - If `free_throws_remaining > 0`: More shots remain → Next free throw
  - If `free_throws_remaining === 0`: Final shot → Rebound OR Inbound
- ✅ **Batch mode**: Uses `ftContext` (ftIndex, ftTotal, bonusType) if `free_throws_remaining` is undefined
  - Single FT → Make/Miss → Rebound OR Inbound
  - 1-and-1 Bonus → First shot → Second shot (if made) OR Rebound (if missed)
  - 2-Shot Bonus → First shot → Second shot (if made) OR Rebound (if missed)
  - 3-Shot Bonus → First → Second → Third → Rebound OR Inbound
  - Set Number → Each shot → Next (if more) OR Rebound/Inbound (if final)
- ✅ **Fixed**: Inbound pass timing (now flips possession before inbound)

### Fast Break Execution Cases:
- ✅ DREB-initiated → Outlet pass → Resolution
- ✅ STEAL-initiated → Resolution (no outlet)
- ✅ Resolution: MAKE, MISS, DEFENSIVE_STOP, FOUL, TURNOVER
- ✅ **Fixed**: Possession flip timing (now flips before inbound)

### OREB Execution Cases:
- ✅ Putback attempt → PUTBACK_MAKE OR PUTBACK_MISS
- ✅ Kickout pass → HCO (no PC)
- ✅ Consecutive OREBs → Batched in same API call
- ✅ Putback with foul → Free throw

### BIP/SIP Execution Cases:
- ✅ BIP (normal) → HCO
- ✅ BIP (FCP setup) → FCP turn
- ✅ BIP (HCT setup) → HCT turn
- ✅ SIP → HCO (always)

---

## Recommendations for Streamlining

### 1. **Unified Skeleton Animation System**
- Create `SkeletonAnimationSystem` that handles:
  - Full skeleton (HCO)
  - Filtered skeleton (FCP/HCT)
  - Step filtering logic
- Parameter: `filterByResultType: boolean`

### 2. **Unified Result Handler**
- Create `ResultHandler` that routes to appropriate handlers:
  - Shot results (MAKE/MISS)
  - Foul results (shooting/non-shooting, bonus/no bonus)
  - Turnover results (dead ball/live ball)
  - Steal results
- Turn-type-specific logic as parameters

### 3. **Unified Inbound System**
- Enhance `runInboundSetup()` to handle:
  - BIP (with FCP/HCT setup)
  - SIP (always HCO)
- Parameter: `inboundType: "baseline" | "side"`

### 4. **Execution Structure Template**
- Define common execution pattern:
  ```typescript
  interface TurnExecution {
    setup: () => Promise<void>;
    animation: () => Promise<void>;
    resultHandling: () => Promise<void>;
  }
  ```
- Each turn type implements this interface

---

## Summary

**Turn Types Covered**: 9 (all from transition registry)

**Execution Patterns Identified**:
1. **Skeleton + Result** (HCO, FCP, HCT) - All use same pattern (AnimationRouter)
2. **Setup + Result** (Free Throw)
3. **Standard Animation** (BIP, SIP, Opening Tip)
4. **Multi-Phase** (Fast Break: outlet + resolution)
5. **Animation + Decision** (OREB: rebound + putback/kickout)

**Code Reuse Opportunities**: 5 major areas identified

**Execution Case Coverage**: All cases documented, some issues identified (FCP/HCT skeleton skipping)

**Next Steps**: 
1. ✅ **Completed**: FCP/HCT now routes through AnimationRouter (unified with HCO) - Verified in code (old FCP/HCT handling commented out in `animateGameTurns.js`, now uses standard AnimationRouter flow)
2. ✅ **Completed**: Unified skeleton animation system (`playTurnAnimation()`) - All turn types (HCO, FCP, HCT) use same skeleton animation system
3. ✅ **Completed**: Unified result handler (AnimationRouter routes to appropriate handlers) - AnimationEngine.determineHandler() routes all turn types to appropriate handlers
4. ⚠️ **Optional Future**: Create execution structure template (optional future enhancement) - Current structure works well, template would be nice-to-have for consistency

