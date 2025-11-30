# Transition Testing Strategy

## Overview

This document outlines the strategy for testing all 45 game state transitions to ensure a truly SS&S transition system.

## Testing Approach: Integration Tests

**Why Integration Tests?**

1. **Real-world validation**: Simulates actual game sequences, catching bugs that unit tests might miss
2. **State management**: Verifies state is correctly managed across multiple turns
3. **Edge case discovery**: Naturally surfaces edge cases (consecutive OREBs, bonus sequences, etc.)
4. **SS&S alignment**: Validates the system as a whole, ensuring stability and scalability

## Test Structure

Each test follows this pattern:

```python
def test_transition_name():
    """Test: [From] -> [To] (PC?) via [Instigating Event]"""
    # 1. Setup: Create game and set initial state
    game = GameManager("Home", "Away")
    game.game_state["offensive_state"] = "[FROM_STATE]"
    
    # 2. Execute: Trigger the transition
    game.simulate_macro_turn()
    result = game.turns[-1]
    
    # 3. Verify: Check transition occurred correctly
    assert game.game_state["offensive_state"] == "[TO_STATE]"
    assert result.get("result_type") == "[EXPECTED_RESULT]"
    assert result.get("possession_flips") == [True/False]
    
    # 4. Verify: Check any separate turns created (inbounds, OREBs)
    if "[EXPECTED_SEPARATE_TURN]":
        assert len(game.turns) >= 2
        assert game.turns[-1].get("result_type") == "[SEPARATE_TURN_TYPE]"
```

## Test Categories

### 1. Opening Tip Transitions (1 test)
- Opening Tip → HCO

### 2. Inbound Pass Transitions (3 tests)
- Inbound Pass → HCO
- Inbound Pass → FCP
- Inbound Pass → HCT

### 3. Side Inbound Pass Transitions (1 test)
- SIP → HCO

### 4. HCO Transitions (8 tests)
- HCO → Inbound Pass (PC): Made Shot, No Foul
- HCO → Free Throw: Made Shot, Foul
- HCO → Free Throw: Missed Shot, Foul
- HCO → Free Throw: Non-Shooting Defensive Foul, Bonus Situation
- HCO → OREB: Missed Shot, OREB
- HCO → HCO (PC): Missed Shot, DREB, HCO next step
- HCO → HCO (PC): Steal, HCO next step
- HCO → Fast Break (PC): Missed Shot, DREB, Fast Break next step
- HCO → Fast Break (PC): Steal, Fast Break next step
- HCO → SIP: Non-Shooting Defensive Foul, No Bonus
- HCO → SIP: Missed Shot, Non-Shooting Defensive Foul
- HCO → SIP (PC): Offensive Foul
- HCO → SIP (PC): Dead Ball Turnover
- HCO → SIP (PC): Missed Shot, Offensive Foul

### 5. OREB Transitions (9 tests)
- OREB → Inbound Pass (PC): Made Shot, No Foul
- OREB → Free Throw: Made Shot, Foul
- OREB → Free Throw: Missed Shot, Foul
- OREB → HCO: Kickout Pass
- OREB → HCO (PC): Missed Shot, DREB, HCO next step
- OREB → Fast Break (PC): Missed Shot, DREB, Fast Break next step
- OREB → OREB: Missed Shot, OREB
- OREB → SIP (PC): Missed Shot, Offensive Foul
- OREB → SIP: Missed shot, Non-Shooting Defensive Foul

### 6. Free Throw Transitions (7 tests)
- Free Throw → Inbound Pass (PC): Final FT Made
- Free Throw → OREB: Final FT Missed, OREB
- Free Throw → HCO (PC): Final FT Missed, DREB, HCO next step
- Free Throw → Fast Break: Final FT Missed, DREB, Fast Break next step
- Free Throw → SIP: Final Free Throw Missed, Defensive Foul, No Bonus Situation
- Free Throw → Free Throw (PC): Final Free Throw Missed, Defensive Foul, Bonus Situation
- Free Throw → SIP (PC): Final Free Throw Missed, Offensive Foul

### 7. Fast Break Transitions (8 tests)
- Fast Break → HCO: Defensive Stop
- Fast Break → Inbound Pass (PC): Made Shot, No Foul
- Fast Break → Free Throw: Made Shot, Foul
- Fast Break → Free Throw: Missed Shot, Foul
- Fast Break → Free Throw: Non-Shooting Defensive Foul, Bonus Situation
- Fast Break → OREB: Missed Shot, OREB
- Fast Break → HCO (PC): Missed Shot, DREB, HCO next step
- Fast Break → HCO (PC): Steal, HCO next step
- Fast Break → Fast Break: Missed Shot, DREB, Fast Break next step
- Fast Break → Fast Break: Steal, Fast Break next step
- Fast Break → SIP: Non-Shooting Defensive Foul, No Bonus Situation
- Fast Break → SIP (PC): Offensive Foul
- Fast Break → SIP (PC): Dead Ball Turnover

### 8. FCP Transitions (8 tests)
- FCP → HCO: Press/Trap Break, HCO next step
- FCP → Inbound Pass: Press/Trap Break, Made Shot Attempt, No Foul
- FCP → Free Throw: Press/Trap Break, Made Shot Attempt, Shooting Foul
- FCP → Free Throw: Press/Trap Break, Missed Shot Attempt, No Foul
- FCP → Free Throw: Non-shooting Defensive Foul, Bonus Situation
- FCP → OREB: Press/Trap Break, Missed Shot Attempt, OREB
- FCP → HCO (PC): Press/Trap Break, Missed Shot Attempt, DREB, HCO next step
- FCP → HCO (PC): Steal, HCO as next step
- FCP → Fast Break (PC): Press/Trap Break, Missed Shot Attempt, DREB, Fast Break next step
- FCP → Fast Break (PC): Steal, Fast Break as next step
- FCP → SIP (PC): Offensive Foul
- FCP → SIP (PC): Dead Ball Turnover
- FCP → SIP: Non-Shooting Defensive Foul

### 9. HCT Transitions (8 tests)
- Same as FCP (8 tests)

**Total: 45 tests** (43 unique + 2 for FCP/HCT separation)

## Test Implementation Strategy

### Phase 1: Core Transitions (Priority 1)
Test the most common transitions first:
- Opening Tip → HCO
- HCO → Inbound Pass (PC)
- HCO → OREB
- HCO → HCO (PC)
- HCO → Fast Break (PC)
- Fast Break → HCO
- Fast Break → Inbound Pass (PC)

### Phase 2: Foul & Turnover Transitions (Priority 2)
- HCO → Free Throw
- HCO → SIP
- Fast Break → Free Throw
- FCP/HCT → Free Throw
- FCP/HCT → SIP

### Phase 3: Edge Cases (Priority 3)
- Free Throw → Free Throw (PC) (rebound foul, bonus)
- Free Throw → SIP (rebound foul, no bonus)
- OREB → SIP (putback foul)
- Consecutive OREBs
- FCP/HCT transitions

## Test Utilities

Create helper functions for common test patterns:

```python
def assert_transition(game, from_state, to_state, possession_change, result_type):
    """Assert that a transition occurred correctly."""
    assert game.game_state["offensive_state"] == to_state
    result = game.turns[-1]
    assert result.get("result_type") == result_type
    assert result.get("possession_flips") == possession_change

def assert_baseline_inbound_created(game):
    """Assert that a baseline inbound turn was created."""
    assert len(game.turns) >= 2
    assert game.turns[-1].get("result_type") == "BASELINE_INBOUND"

def assert_side_inbound_created(game):
    """Assert that a side inbound turn was created."""
    assert len(game.turns) >= 2
    assert game.turns[-1].get("result_type") == "SIDE_INBOUND"
```

## Running Tests

```bash
# Run all transition tests
pytest tests/test_transition_system.py -v

# Run specific category
pytest tests/test_transition_system.py::TestHCOTransitions -v

# Run with coverage
pytest tests/test_transition_system.py --cov=BackEnd --cov-report=html
```

## Success Criteria

✅ All 45 transitions have passing tests
✅ Each test verifies: `offensive_state`, `possession_flips`, separate turn creation
✅ Edge cases (rebound fouls, consecutive OREBs) are covered
✅ Tests run in < 30 seconds total
✅ 100% transition coverage (all paths tested)

