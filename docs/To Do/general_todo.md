# General To-Do List

This document tracks general improvements and features that don't warrant their own dedicated planning documents.

## Energy System

### Holistic Energy Decay System Implementation
**Status:** Pending  
**Priority:** Medium  
**Description:**  
Currently, energy decay only happens during HCO turns. Energy decay should be applied consistently across all turn types (Fast Break, FCP, HCT, OREB, Free Throw) to ensure players fatigue properly throughout the game.

**Current State:**
- Energy decay implemented for HCO turns only (via `apply_energy_decay()` in `phase_resolution.py`)
- Other turn types (Fast Break, FCP, HCT, OREB, Free Throw) do not apply energy decay
- `determine_event_type()` still contains energy decay logic but is rarely called

**Future Work:**
- Extract energy decay to be called for all turn types
- Determine appropriate decay amounts for different turn types (e.g., Fast Break might have higher decay than Free Throw)
- Ensure energy decay is applied consistently regardless of turn outcome

**Related Files:**
- `BackEnd/engine/phase_resolution.py` - `apply_energy_decay()` function
- `BackEnd/models/turn_manager.py` - `determine_event_type()` method (contains legacy energy decay)
- `BackEnd/models/player.py` - `decay_energy()` and `get_fatigue_decay_amount()` methods

---

## Animation System

### Improved HCO Steal Animations for Shot Attempts and Defensive Stops
**Status:** Pending  
**Priority:** Medium  
**Description:**  
HCO steal animations need improvement for both shot attempt and defensive stop outcomes. Currently, the animations may not feel organic or properly synchronized.

**Current State:**
- HCO steals can result in Fast Break (shot attempt or defensive stop)
- Steal Entry step exists for Fast Break transitions
- Animation timing and feel may need refinement

**Future Work:**
- Review and improve steal animation timing for shot attempts
- Review and improve steal animation timing for defensive stops
- Ensure animations feel more human and organic
- Verify proper ball attachment and player positioning during steal transitions

**Related Files:**
- `BackEnd/engine/phase_resolution.py` - `resolve_turnover_logic()` (HCO steals)
- `FrontEnd/static/js/phaser/animation/fastBreak.js` - Fast Break animations
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - Turn animation orchestration

---

## Notes

- Items are added here when they don't warrant a full planning document
- Items can be moved to dedicated planning documents if they become more complex
- Priority levels: High, Medium, Low

