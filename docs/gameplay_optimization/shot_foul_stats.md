# Shot and Foul Statistics Archive

This document archives shot attempt and foul statistics from gameplay simulations.

---

## Test 1

**Date:** January 2025  
**Games Simulated:** 20  
**Total Shot Attempts:** 904  
**Total HCO Turns:** 1,558

### Shot Attempt Statistics

| Metric | Value |
|--------|-------|
| Total Shot Attempts | 904 |
| Shot Attempt Rate | 22.55% of all turns |
| Shot Attempts per Game | ~45.2 |

### Foul Statistics

| Metric | Value |
|--------|-------|
| Shooting Fouls | 110 |
| Shooting Foul Rate | 12.17% of shot attempts |
| AND-1 Opportunities | 0 |

### Foul Breakdown (Non-Shooting)

| Foul Type | Count | Percentage of HCO Results |
|-----------|-------|--------------------------|
| O_FOUL (Offensive Foul) | 108 | 8.39% |
| D_FOUL (Non-Shooting Defensive Foul) | 142 | 11.02% |
| **Total Non-Shooting Fouls** | **250** | **19.41%** |

### Observations

- **Shooting Foul Rate**: 12.17% of shot attempts is within a reasonable range for basketball
- **Non-Shooting Fouls**: 250 total (19.41% of HCO results)
  - Offensive fouls: 108 (8.39%)
  - Defensive fouls (non-shooting): 142 (11.02%)
- **AND-1 Opportunities**: 0 instances in this sample (no made shots with shooting fouls)

### System Status

✅ **Shooting Foul System**: Implementation complete
- Hard/soft thresholds with foul calibration
- Foul calibration check forces misses (90% for 3-pointers, 50% for 2-pointers)
- Integration with shot resolution

