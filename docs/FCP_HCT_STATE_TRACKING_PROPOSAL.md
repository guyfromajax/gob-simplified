# FCP/HCT State Tracking Proposal

## Problem
Current FCP/HCT detection is fragile and unreliable:
- Complex flag detection logic scattered across multiple files
- Relies on backend flags that may or may not be present
- Inheritance logic is error-prone
- Hard to debug and maintain

## Solution: Scene-Level State Tracking

### Core Concept
Track FCP/HCT state in the scene object, similar to how we track other game state.

### Implementation

#### 1. Initialize State in Scene
```javascript
// In gameScene.js or animateGameTurns.js
scene.currentPressureType = null; // "FCP" | "HCT" | null
scene.pressureSequenceActive = false; // Track if we're in a pressure sequence
```

#### 2. Set State When FCP/HCT Setup Detected
```javascript
// When BASELINE_INBOUND has next_defensive_setup === "FCP" or "HCT"
if (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT") {
  scene.currentPressureType = turn.next_defensive_setup;
  scene.pressureSequenceActive = true;
  console.log(`🎯 [FCP/HCT STATE] Setting pressure type: ${scene.currentPressureType}`);
}
```

#### 3. Use State for Routing (Instead of Complex Flag Detection)
```javascript
// Simple check - if we're in a pressure sequence, route to FCP/HCT handler
const isFCPHCT = scene.pressureSequenceActive && 
                 (turn.fcp_shot || turn.hct_shot || 
                  turn.fcp_foul || turn.hct_foul ||
                  turn.result_type === "MAKE" || turn.result_type === "MISS" ||
                  turn.result_type === "HCO" || turn.result_type === "TURNOVER");
```

#### 4. Clear State When Sequence Completes
```javascript
// Clear when:
// - Shot attempt completes (MAKE/MISS)
// - Foul occurs
// - Turnover occurs
// - Transition to HCO (pressure broken)
// - Any non-pressure outcome

if (turn.result_type === "HCO" && !turn.fcp_shot && !turn.hct_shot) {
  // Pressure broken, transition to HCO
  scene.currentPressureType = null;
  scene.pressureSequenceActive = false;
  console.log(`🎯 [FCP/HCT STATE] Clearing - pressure broken, transitioning to HCO`);
}
```

### Benefits
1. **Simple**: One source of truth (scene state)
2. **Reliable**: Doesn't depend on backend flags being present
3. **Maintainable**: Easy to debug and understand
4. **Consistent**: Same logic everywhere

### Migration Path
1. Add state tracking to scene
2. Set state when FCP/HCT setup detected
3. Replace complex flag detection with simple state check
4. Clear state when sequence completes
5. Remove old complex detection logic

### Example Flow
```
Turn 1: BASELINE_INBOUND (next_defensive_setup: "FCP")
  → Set scene.currentPressureType = "FCP"
  → Set scene.pressureSequenceActive = true

Turn 2: MISS (fcp_shot: true)
  → Check: scene.pressureSequenceActive === true → Route to FCP handler
  → Animate FCP press break + shot

Turn 3: HCO (pressure broken)
  → Clear scene.currentPressureType = null
  → Clear scene.pressureSequenceActive = false
  → Route to HCO handler
```

