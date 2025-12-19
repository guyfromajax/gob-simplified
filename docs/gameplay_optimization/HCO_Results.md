# HCO Results Archive

This document archives HCO (Half Court Offense) resolution statistics from gameplay simulations.

---

## Test 1

**Date:** December 19, 2025  
**Games Simulated:** 20  
**Total HCO Turns:** 1,558 (77.9 HCO turns per game)  
**Total Turns Processed:** 4,009 across all turn types

### HCO Results Breakdown

| Outcome | Count | Percentage |
|---------|-------|------------|
| Shot Attempt | 904 | 70.19% |
| O_FOUL (Offensive Foul) | 108 | 8.39% |
| D_FOUL (Non-Shooting Defensive Foul) | 142 | 11.02% |
| DEAD_BALL_TURNOVER | 60 | 4.66% |
| STEAL | 74 | 5.75% |
| **Total HCO Results** | **1,288** | **100%** |

### Observations

- Shot attempts dominate HCO outcomes (~70%), which aligns with expected basketball flow
- Dead ball turnovers are being tracked correctly: 60 instances (4.66%)
- Foul distribution: 8.39% offensive, 11.02% defensive (non-shooting)
- Steals: 74 instances (5.75%)
- Shot Attempt Rate: 22.55% of all turns

### System Status

✅ **HCO Resolution System**: Implementation complete
- Modular functions for fouls, steals, and turnovers
- Randomized execution order for event checks (Steps 3-5)
- Respects resolution system determination (prevents random conversion of dead ball turnovers)
- Nomenclature conversion: `DEAD_BALL_TURNOVER` → `"DEAD BALL"` when calling `resolve_turnover_logic()`

---

## Test 2

**Date:** December 19, 2025  
**Games Simulated:** 20  
**Total HCO Turns:** 1,629 (81.5 HCO turns per game)  
**Total Turns Processed:** 4,487 across all turn types

### HCO Results Breakdown

| Outcome | Count | Percentage |
|---------|-------|------------|
| Shot Attempt | 844 | 67.95% |
| O_FOUL (Offensive Foul) | 116 | 9.34% |
| D_FOUL (Non-Shooting Defensive Foul) | 183 | 14.73% |
| DEAD_BALL_TURNOVER | 48 | 3.86% |
| STEAL | 51 | 4.11% |
| **Total HCO Results** | **1,242** | **100%** |

### Observations

- Shot attempts: 67.95% (slightly lower than Test 1's 70.19%)
- Dead ball turnovers: 48 instances (3.86%, slightly lower than Test 1's 4.66%)
- Foul distribution: 9.34% offensive, 14.73% defensive (non-shooting) - defensive fouls higher than Test 1
- Steals: 51 instances (4.11%, lower than Test 1's 5.75%)
- Shot Attempt Rate: 18.81% of all turns (lower than Test 1's 22.55%)

---

## Test 3

**Date:** January 2025  
**Games Simulated:** 20  
**Total HCO Turns:** 1,607 (80.3 HCO turns per game)  
**Total Turns Processed:** 4,369 across all turn types

### HCO Results Breakdown

| Outcome | Count | Percentage |
|---------|-------|------------|
| Shot Attempt | 884 | 70.27% |
| O_FOUL (Offensive Foul) | 119 | 9.46% |
| D_FOUL (Non-Shooting Defensive Foul) | 146 | 11.61% |
| DEAD_BALL_TURNOVER | 59 | 4.69% |
| STEAL | 50 | 3.97% |
| **Total HCO Results** | **1,258** | **100%** |

### Observations

- Shot attempts: 70.27% (similar to Test 1's 70.19%, higher than Test 2's 67.95%)
- Dead ball turnovers: 59 instances (4.69%, similar to Test 1's 4.66%, higher than Test 2's 3.86%)
- Foul distribution: 9.46% offensive, 11.61% defensive (non-shooting) - balanced between Test 1 and Test 2
- Steals: 50 instances (3.97%, lower than both Test 1's 5.75% and Test 2's 4.11%)
- Shot Attempt Rate: 20.23% of all turns (between Test 1's 22.55% and Test 2's 18.81%)

