# test_shared_defense.py Import Failure

**Status:** To fix later  
**Impact:** Test suite only — no user-facing bug. Production code does not use the removed functions.

---

## What Happens

`pytest` fails during **collection** when running `tests/test_shared_defense.py`:

```
ImportError: cannot import name 'assign_non_bh_defender_coords' from 'BackEnd.utils.shared_defense'
```

The test file also imports `assign_bh_defender_coords`, which is similarly missing.

---

## Do We Use These in Production?

**No.** Production code does **not** call these functions.

- **BackEnd/utils/shared_defense.py** (lines 6–8) states that `assign_bh_defender_coords()` and `assign_non_bh_defender_coords()` **have been removed**. Call sites now use the unified `get_defender_coords()` system.
- **BackEnd/models/animator.py** only mentions them in **comments** (e.g. lines 987, 1018, 1608, 1760); there are no imports or runtime calls.
- The only place that imports and calls these symbols is **tests/test_shared_defense.py**.

So this is a **stale test**: the tests were not updated when the old API was removed. Users are not affected.

---

## Root Cause

The tests in `test_shared_defense.py` were written for the previous defender-coord API. During refactor (PHASE 6), `assign_bh_defender_coords` and `assign_non_bh_defender_coords` were removed from `shared_defense.py` and replaced by `get_defender_coords()`. The test file was left still importing and testing the removed functions.

---

## Next Steps (when we return to this)

1. **Option A:** Remove or skip the tests that rely on `assign_non_bh_defender_coords` and `assign_bh_defender_coords` (e.g. `test_assign_non_bh_defender_coords_away_mirrors_home_spacing`, `test_assign_bh_defender_coords_away_mirrors_home_spacing`, `test_baseline_defense_vertical_not_flipped`, and any others that call these functions).
2. **Option B:** Re-express the same behavioral guarantees (e.g. away mirrors home spacing, baseline vertical not flipped) using the current API (`get_defender_coords()` and related helpers) and update the tests to call that instead.
3. Ensure no other tests in that file depend on the removed functions; fix or remove those as well so the full test suite can collect and run.
