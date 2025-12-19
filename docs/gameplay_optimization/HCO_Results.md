# HCO Results Archive

This document archives HCO (Half Court Offense) resolution statistics from gameplay simulations.

---

## Test 1

**Date:** January 2025  
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

