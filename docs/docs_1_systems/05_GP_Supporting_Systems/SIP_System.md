## SIDE_INBOUND (SIP) System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Trigger Conditions**:
   - After dead ball situations: fouls (non-shooting), dead ball turnovers, or other stoppages
   - Next turn is always `SIDE_INBOUND`
   - Simpler than BASELINE_INBOUND (no defensive pressure setup or retreat animations)

2. **Player Positioning**:
   - **Offensive Players**: Positions from `turnData.oDestinations` (backend-provided random ranges)
   - **Defensive Players**: Positions from `turnData.dDestinations` (backend-provided fixed positions)
   - **Inbounder**: SF stays at inbound spot (`ball_spot`)

3. **Ball Handling**:
   - **Ball Positioning**: Ball immediately moved to `ball_spot` coordinates at turn start
   - **Ball Attachment**: Ball attaches to SF when SF reaches inbound spot (in SF's tween `onComplete` callback)
   - **Inbound Pass**: SF → PG (hardcoded fallback, or dynamic from `turnData.animations`)

**SIP System Flow (8 Steps)**

1. **Dead Ball Situation Occurs** - Foul, turnover, or other stoppage
2. **SIP Turn Created** - Backend creates `SIDE_INBOUND` turn with player positions
3. **Frontend Routing** - `AnimationEngine.handleSideInbound()` routes the turn
4. **Ball Positioning** - Ball immediately moved to inbound spot
5. **Player Positioning** - Players animate to positions from `oDestinations` and `dDestinations`
6. **Ball Attachment** - Ball attaches to SF when SF reaches inbound spot
7. **Inbound Pass Execution** - Inbound pass animation completes (SF → PG)
8. **Next Turn Begins** - HCO turn starts (typically)

**Long Form Documentation**

### Overview

Side inbound passes (`SIDE_INBOUND`) occur after dead ball situations such as fouls (non-shooting), turnovers (dead ball), or other stoppages. Unlike BASELINE_INBOUND, SIP is simpler and doesn't involve defensive pressure setup or retreat animations.

**Location:** `BackEnd/models/turn_manager.py` - `setup_side_inbound()`, `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleSideInbound()`  
**Status:** ✅ Fully implemented with simple positioning and pass execution  
**Scope:** Player positioning and inbound pass execution after dead ball situations

### Process Overview

**Location:** `AnimationEngine.handleSideInbound()` → `PassAnimationSystem.executeInboundSequence()` → `runSideInboundSetup()`

**Flow:**
1. Dead ball situation occurs (foul, turnover, etc.)
2. `SIDE_INBOUND` turn is created by backend
3. Frontend routes to `AnimationEngine.handleSideInbound()`
4. Ball is immediately moved to inbound spot
5. Players are positioned based on `oDestinations` and `dDestinations`
6. Ball attaches to SF when SF reaches the inbound spot
7. Inbound pass is executed (SF → PG)
8. Next turn (typically HCO) begins

**State Guard Note (Current Behavior):**
- SIP pass execution is not gated by `FastBreak` state.
- If state lingers from a prior fast-break sequence, SIP still runs and then normalizes to HalfCourt at turn end.

### Ball Handling

**Ball Positioning:**
- Ball is immediately moved to `ball_spot` coordinates at the start of the SIP turn
- Ball remains at the inbound spot while players animate to their positions
- This matches BASELINE_INBOUND behavior for consistency

**Ball Attachment:**
- Ball attaches to SF when SF reaches the inbound spot (in SF's tween `onComplete` callback)
- This ensures the ball is attached as soon as the SF arrives, not after all players finish
- Safety fallback attachment exists if SF tween completes without attachment

**Key Code:**
- `turnAnimation.js` lines 294-301: Ball immediately positioned at inbound spot
- `turnAnimation.js` lines 321-327: Ball attaches to SF when SF reaches spot
- `turnAnimation.js` lines 378-384: Safety fallback attachment check

### Player Positioning

**Offensive Players:**
- Positions come from `turnData.oDestinations` (backend-provided)
- All offensive players animate to their destinations using distance-based timing
- SF is the inbounder (receives ball at inbound spot)
- **Position Ranges (Home Orientation):**
  - PG: x=(50, 54), y=(37, 43)
  - SG: x=(55, 64), y=(18, 32)
  - PF: x=(65, 80), y=(26, 36)
  - C: x=(65, 80), y=(14, 24)
  - SF: Inbound spot (x=47, y=48) - stays at inbound spot

**Defensive Players:**
- Positions come from `turnData.dDestinations` (backend-provided)
- All defensive players animate to their destinations using distance-based timing
- No special retreat or pressure positioning (unlike BIP)
- **Fixed Positions (Home Orientation):**
  - PG: x=60, y=25
  - SG: x=64, y=33
  - SF: x=66, y=17
  - PF: x=80, y=25
  - C: x=85, y=28

**Coordinate Flipping:**
- Away team offense/defense: Coordinates flipped using `getAwayTeamCoords()` function
- Formula: `x = 101 - x` (flips around midcourt)

### Inbound Pass Execution

**Pass Detection:**
- Frontend checks `turnData.animations` for dynamic pass actions
- If pass detected in animation data, uses `handlePassAnimation()` with pass info
- Falls back to hardcoded SF → PG pass if no pass detected

**Pass Animation:**
- Pass executes after all players reach their positions
- Ball transfers from SF to PG
- PG receives ball and next turn begins

**Key Code:**
- `turnAnimation.js` lines 359-415: Pass detection and execution
- `passDetection.js`: Dynamic pass detection from animation data
- `ballManager.js`: Pass animation execution

### Key Differences from BASELINE_INBOUND

| Aspect | SIDE_INBOUND (SIP) | BASELINE_INBOUND (BIP) |
|--------|-------------------|------------------------|
| **Use Case** | After fouls, dead ball turnovers | After made shots, quarter starts |
| **Defensive Setup** | Simple positioning from `dDestinations` | Complex: retreat animation or FCP/HCT press positions |
| **Pressure Logic** | None | Handles FCP/HCT setup with skeleton positions |
| **Ball Attachment** | Attaches when SF reaches spot | Attaches after all players positioned |
| **Complexity** | Simple, straightforward | Complex with multiple scenarios |
| **Code Function** | `runSideInboundSetup()` | `runInboundSetup()` |

### Key Functions

**Backend:**
- `turn_manager.py` `setup_side_inbound()`: Creates SIDE_INBOUND turn data with `oDestinations`, `dDestinations`, `ball_spot`
  - Generates random offensive positions within defined ranges
  - Sets fixed defensive positions
  - Handles coordinate flipping for away team

**Frontend:**
- `AnimationEngine.handleSideInbound()`: Routes SIDE_INBOUND turns
- `PassAnimationSystem.executeInboundSequence()`: Handles inbound pass execution
- `turnAnimation.js` `runSideInboundSetup()`: Positions players, handles ball attachment, executes inbound pass

### Key Files

**Backend:**
- `BackEnd/models/turn_manager.py` - `setup_side_inbound()` method (lines 63-137)

**Frontend:**
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleSideInbound()` method
- `FrontEnd/static/js/phaser/animation/PassAnimationSystem.js` - `executeInboundSequence()` method
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `runSideInboundSetup()` function (lines 393-415)
