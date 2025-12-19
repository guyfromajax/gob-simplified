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
- Foul calibration check forces misses (40% for 3-pointers, 20% for 2-pointers)
- Integration with shot resolution
- Calibration thresholds stored as constants: `THREE_POINTER_FOUL_MISS_CHANCE = 0.4`, `TWO_POINTER_FOUL_MISS_CHANCE = 0.2`

---

## Test 2

**Date:** January 2025  
**Games Simulated:** 20  
**Total Shot Attempts:** 844  
**Total HCO Turns:** 1,629

### Shot Attempt Statistics

| Metric | Value |
|--------|-------|
| Total Shot Attempts | 844 |
| Shot Attempt Rate | 18.81% of all turns |
| Shot Attempts per Game | ~42.2 |

### Foul Statistics

| Metric | Value |
|--------|-------|
| Shooting Fouls | 135 |
| Shooting Foul Rate | 16.00% of shot attempts |
| AND-1 Opportunities | 0 |

### Foul Breakdown (Non-Shooting)

| Foul Type | Count | Percentage of HCO Results |
|-----------|-------|--------------------------|
| O_FOUL (Offensive Foul) | 116 | 9.34% |
| D_FOUL (Non-Shooting Defensive Foul) | 183 | 14.73% |
| **Total Non-Shooting Fouls** | **299** | **24.07%** |

### Observations

- **Shooting Foul Rate**: 16.00% of shot attempts (higher than Test 1's 12.17%)
- **Non-Shooting Fouls**: 299 total (24.07% of HCO results, higher than Test 1's 19.41%)
  - Offensive fouls: 116 (9.34%, higher than Test 1's 8.39%)
  - Defensive fouls (non-shooting): 183 (14.73%, higher than Test 1's 11.02%)
- **AND-1 Opportunities**: 0 instances in this sample (no made shots with shooting fouls)
- **Shot Attempts**: 844 total (lower than Test 1's 904)

---

## Test 3

**Date:** January 2025  
**Games Simulated:** 20  
**Total Shot Attempts:** 884  
**Total HCO Turns:** 1,607

### Shot Attempt Statistics

| Metric | Value |
|--------|-------|
| Total Shot Attempts | 884 |
| Shot Attempt Rate | 20.23% of all turns |
| Shot Attempts per Game | ~44.2 |

### Foul Statistics

| Metric | Value |
|--------|-------|
| Shooting Fouls | 85 |
| Shooting Foul Rate | 9.62% of shot attempts |
| AND-1 Opportunities | 0 |

### Foul Breakdown (Non-Shooting)

| Foul Type | Count | Percentage of HCO Results |
|-----------|-------|--------------------------|
| O_FOUL (Offensive Foul) | 119 | 9.46% |
| D_FOUL (Non-Shooting Defensive Foul) | 146 | 11.61% |
| **Total Non-Shooting Fouls** | **265** | **21.07%** |

### Observations

- **Shooting Foul Rate**: 9.62% of shot attempts (lower than both Test 1's 12.17% and Test 2's 16.00%)
- **Non-Shooting Fouls**: 265 total (21.07% of HCO results, between Test 1's 19.41% and Test 2's 24.07%)
  - Offensive fouls: 119 (9.46%, higher than Test 1's 8.39%, similar to Test 2's 9.34%)
  - Defensive fouls (non-shooting): 146 (11.61%, between Test 1's 11.02% and Test 2's 14.73%)
- **AND-1 Opportunities**: 0 instances in this sample (no made shots with shooting fouls)
- **Shot Attempts**: 884 total (similar to Test 1's 904, higher than Test 2's 844)

