# Game Time vs Real Time — Side-by-Side by Turn Type

This document compares **game time** (`time_elapsed`, game seconds) and **real time** (`real_time_elapsed_ms`, wall-clock ms) for every turn so we can sync every real-time phase to game time unless explicitly excluded (e.g. rim hold on makes).

**Bridge:** 1 game second = 350 ms real time (movement only).  
**Real-time formula:** `real_time_elapsed_ms = (time_elapsed × 350) + fixed_phases_ms`

---

## 1. HCO / Half-court shot (MAKE, MISS, BLOCK)

| Component | Game time (backend) | Real time (frontend / _compute_real_time_elapsed_ms) | Synced? |
|-----------|---------------------|-------------------------------------------------------|---------|
| **Movement (skeleton steps)** | Yes. `calc_skeleton_step_timing_contract(steps, shot_step_index)` → `step_clock_seconds` per step (1 s each, step0 may have bringup). Sum → `time_elapsed`. | Yes. `movement_ms = time_elapsed × 350`. | ✅ |
| **Pass before shot (pass_delay)** | **No.** Not in skeleton; no extra game seconds. | Yes. 150 ms (animation_config `pass.duration`). | ❌ Real only |
| **Rim hold (miss/block)** | **No.** Not in skeleton. | Yes. 1000 ms (animation_config `shot.rimHoldMs`). | ❌ Real only |
| **Rim hold (make)** | No. | **Excluded by design** (clock paused on makes). | ✅ N/A |

**Summary:** Game time = skeleton steps only. Real time adds **150 ms** (pass) and **1000 ms** (rim on miss) with no game-time equivalent. To sync: either add ~0 game s for 150 ms pass and ~1 game s for 1000 ms rim-on-miss, or document as intentional real-only.

---

## 2. FCP / HCT (steal then shot or turnover/foul)

| Component | Game time (backend) | Real time | Synced? |
|-----------|---------------------|-----------|---------|
| **Movement (skeleton steps)** | Yes. `calc_skeleton_step_timing_contract(steps, resolution_step_index)` for FCP/HCT phase. | `movement_ms = time_elapsed × 350`. | ✅ |
| **Steal / pass phase** | **No.** Not a separate game second. | 150 ms (animation_config `steal.duration`). | ❌ Real only |
| **Rim hold (miss)** | No. | 1000 ms (same as HCO). | ❌ Real only |
| **Rim hold (make)** | No. | Excluded by design. | ✅ N/A |

**Summary:** Same as HCO: **150 ms** (steal) and **1000 ms** (rim on miss) are real-only.

---

## 3. Fast break — shot (MAKE / MISS / BLOCK)

| Component | Game time (backend) | Real time | Synced? |
|-----------|---------------------|-----------|---------|
| **Movement (distance)** | Yes. `_apply_fast_break_cg_time`: `distance_seconds` from `calc_cg_segment_seconds` along path. | `movement_ms = time_elapsed × 350` (includes overhead below). | ✅ |
| **Outlet pass** | Yes. +1 game s if `outlet_passer`. | 250 ms (animation_config `fastBreak.passMs`). | ⚠️ Backend 1 s (350 ms); real 250 ms |
| **Outlet receiver move** | Yes. +1 game s if `outlet_receiver`. | 300 ms (`fastBreak.outletMoveMs`). | ⚠️ Backend 1 s (350 ms); real 300 ms |
| **Shot attempt** | Yes. +1 game s if `shot_attempted`. | 500 ms (`fastBreak.shotMs`). | ⚠️ Backend 1 s (350 ms); real 500 ms |
| **Rim hold (miss)** | **No.** | 1000 ms. | ❌ Real only |
| **Rim hold (make)** | No. | Excluded by design. | ✅ N/A |

**Summary:** Backend uses 3 flat game seconds for pass + receiver + shot (= 1050 ms at 350 ms/s). Real time uses 250 + 300 + 500 = 1050 ms. Totals match; per-phase mapping differs (game uses 1 s each, real uses exact ms). Rim on miss **1000 ms** is real-only.

---

## 4. Fast break — DEFENSIVE_STOP

| Component | Game time (backend) | Real time | Synced? |
|-----------|---------------------|-----------|---------|
| **Movement + outlet** | Yes. `_apply_fast_break_cg_time(result, shot_attempted=False)`: distance + 1 (outlet_passer) + 1 (outlet_receiver). No shot second. | `movement_ms = time_elapsed × 350`. | ✅ |
| **Defensive stop hold** | **No.** No extra game second for the hold. | 1000 ms (`fastBreak.defensiveStopHoldMs`). | ❌ Real only |

**Summary:** **1000 ms** stop hold is real-only; no game second for it.

---

## 5. OREB — PUTBACK_MAKE / PUTBACK_MISS / OREB_KICKOUT

| Component | Game time (backend) | Real time | Synced? |
|-----------|---------------------|-----------|---------|
| **“Possession” time** | Yes. `time_elapsed` = `oreb_event.get("timeElapsed", random.randint(1, 5))` or kickout `random.randint(1, 5)`. No per-phase breakdown. | `movement_ms = time_elapsed × 350`. | ✅ |
| **Rebound move (collapse)** | **No.** Not broken out in backend. | 300 ms (`rebound.playerMoveMs`). | ❌ Real only |
| **Attach delay** | **No.** | 500 ms (`rebound.attachDelayMs`). | ❌ Real only |
| **Rim hold (putback miss)** | No. | 1000 ms (same rim hold). | ❌ Real only |
| **Rim hold (putback make)** | No. | Excluded by design. | ✅ N/A |

**Summary:** **300 ms** (rebound move) and **500 ms** (attach delay) and **1000 ms** (rim on putback miss) are real-only. Game time is a single 1–5 s (or from event) for the whole OREB.

---

## 6. FOUL (non-shooting, e.g. O_FOUL, D_FOUL in HCO)

| Component | Game time (backend) | Real time | Synced? |
|-----------|---------------------|-----------|---------|
| **Skeleton or fallback** | Yes. `resolve_non_shooting_foul`: skeleton `calc_skeleton_step_timing_contract` or `random.randint(1, 5)` or `time_elapsed_override`. | `movement_ms = time_elapsed × 350`. | ✅ |
| **Fixed phases** | N/A. | 0 ms (we use fixed_ms = 0). | ✅ |

**Summary:** No fixed real-time phases; game time only.

---

## 7. OPENING_TIP

| Component | Game time (backend) | Real time | Synced? |
|-----------|---------------------|-----------|---------|
| **Tip “possession” time** | Yes. `time_elapsed = random.randint(1, 5)` (opening_tip.py). | `movement_ms = time_elapsed × 350`. | ✅ |
| **Initial hold** | **No.** (Clock not started yet.) | Excluded by design (2000 ms in frontend; we don’t count it in real_time_elapsed_ms). | ✅ N/A |
| **Apex delay** | **No.** | 100 ms (from prompt; may be in frontend config). | ❌ Real only |
| **Pass delay** | **No.** | 300 ms (prompt / apex + pass). We use fixed 400 ms total (apex + pass). | ❌ Real only |

**Summary:** **400 ms** (apex_delay + pass_delay) is real-only; game time is only the 1–5 s tip time.

---

## 8. FINAL_HOLD (final turn shot, clock drains to 0)

| Component | Game time (backend) | Real time | Synced? |
|-----------|---------------------|-----------|---------|
| **Movement + shot** | Yes. `time_elapsed = time_remaining` (full drain to 0). Skeleton steps to shot. | `movement_ms = time_elapsed × 350`. | ✅ |
| **Hold at 0 (holdClockOutMs)** | **No.** Clock already 0; no extra game seconds. | 1800 ms (`finalTurn.holdClockOutMs`). | ❌ Real only |

**Summary:** **1800 ms** hold-at-zero is real-only; game time is already the full drain.

---

## 9. Zero-elapsed turns (FREE_THROW, SIDE_INBOUND, BASELINE_INBOUND, TIMEOUT)

| Component | Game time (backend) | Real time | Synced? |
|-----------|---------------------|-----------|---------|
| **Any** | 0. | 0. | ✅ |

---

## 10. STEAL / DEAD BALL / TURNOVER / CHARGE (no shot)

| Component | Game time (backend) | Real time | Synced? |
|-----------|---------------------|-----------|---------|
| **Skeleton steps** | Yes. From `calc_skeleton_step_timing_contract` in phase_resolution (turnover/foul paths). | `movement_ms = time_elapsed × 350`. | ✅ |
| **Fixed phases** | N/A. | 0 ms (we use fixed_ms = 0). | ✅ |

**Summary:** No fixed real-time phases; game time only.

---

## Summary: Real-time phases that do NOT expire game time

| Phase | Turn type(s) | Real (ms) | Game time? | Note |
|-------|----------------|----------|------------|------|
| Pass before shot (pass_delay) | HCO | 150 | No | Could add ~0.43 s (150/350) to sync. |
| Steal phase | FCP/HCT | 150 | No | Same. |
| Rim hold (miss/block) | HCO, FCP, HCT, FB, putback miss | 1000 | No | Could add 1 s (or 1000/350 ≈ 2.86 s) to sync. |
| Rim hold (make) | All makes | — | No | **Excluded by design** (clock paused). |
| Outlet pass (FB) | Fast break | 250 | Yes (1 s) | Backend 350 ms equivalent; real 250 ms. |
| Outlet move (FB) | Fast break | 300 | Yes (1 s) | Backend 350 ms equivalent; real 300 ms. |
| Shot phase (FB) | Fast break | 500 | Yes (1 s) | Backend 350 ms equivalent; real 500 ms. |
| Defensive stop hold | DEFENSIVE_STOP | 1000 | No | Could add ~1 s to sync. |
| Rebound move (OREB) | OREB / putback | 300 | No | Could add to OREB game time. |
| Attach delay (OREB) | OREB / putback | 500 | No | Same. |
| Apex + pass (opening tip) | OPENING_TIP | 400 | No | Could add ~1 s to sync. |
| Hold at 0 (final) | FINAL_HOLD | 1800 | No | Clock already 0; optional to add game time. |
| Initial hold (opening tip) | OPENING_TIP | 2000 | No | **Excluded by design** (clock not started). |

---

## Recommendation: sync real → game unless excluded

- **Excluded by design (do not add game time):**  
  Rim hold on makes, opening tip initial_hold.

- **Consider adding game time so real and game stay in sync:**  
  Pass delay (150 ms → ~0.43 s or round to 1 s), rim hold on miss (1000 ms → 1 s or ~2.86 s), defensive stop hold (1000 ms → 1 s), OREB rebound_move (300 ms) + attach_delay (500 ms) (e.g. 1 s total), opening tip apex+pass (400 ms → ~1 s), and optionally final hold (1800 ms → 0 or leave as real-only once clock is 0).

- **Fast break:**  
  Totals already align (3 s game vs 250+300+500 ms real). Per-phase sync would require either changing backend to use fractional seconds for pass/receiver/shot or accepting the current 1 s per phase as “close enough.”

---

*Source: backend `time_elapsed` (turn_manager, shot_manager, phase_resolution, shared.py, opening_tip, rebound_manager), frontend `_compute_real_time_elapsed_ms` and `animation_config.js`.*
