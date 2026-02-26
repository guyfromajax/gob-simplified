# Shot Clock Audit and Work Plan

**Source of truth:** `Real_Time_Clock_System.md` (this folder).  
**Goal:** Backend is single source of authority for shot clock; frontend is dumb display only.

---

## 1. Doc rules (summary)

- **§92–96:** Backend `time_elapsed`, `time_remaining`, `clock` are authoritative; frontend countdown is UX only; one turn response syncs clock at turn boundaries.
- **§101–102 (Live clock end-of-turn snap):** Frontend snaps shot clock from **turn’s** `shot_clock_remaining` when present, else **`shot_clock_end`** (contract). “No extra backend fields; **reset and shot-clock violation remain backend-only**.”
- **§212–223 (Backend: shot clock derivation):** Backend derives `shot_clock_end`; attach contract; **then** if reset, set `game_state["shot_clock_remaining"] = 30` (or min(30, time_remaining)) for **next** turn. Order: compute end → attach contract → then reset.
- **§225–235 (Shot clock reset instances):** All shot attempts, offensive foul, defensive foul, steal, dead ball turnover, shot clock violation.

---

## 2. Backend audit

### 2.1 Where shot clock is set (game state)

| Location | What it does | Doc‑aligned? |
|----------|----------------|-------------|
| **turn_manager.update_clock_and_possession** | Sets `raw_shot_end` from turn, then `_attach_clock_contract`, then if `_should_reset_shot_clock(result)` sets `game_state["shot_clock_remaining"] = min(30, clock_end)`. | ✅ Order matches doc (contract then reset). Reset rule includes D_FOUL→SIP, O-foul, DEAD BALL, etc. |
| **game_manager (after SIP)** | After appending SIP and setting `offensive_state = "HCO"`, sets `game_state["shot_clock_remaining"] = min(30, time_remaining)`. | ✅ Explicit “after SIP → 30” (or cap). Redundant with turn_manager reset for FOUL but ensures next HCO sees 30. |
| **main.py** | Various one-off paths (e.g. `gm.game_state["shot_clock_remaining"] = min(30, int(new_time))`). | ⚠️ Scattered; should be consistent with turn_manager/game_manager rules. |
| **api.py (timeout resume, DB load)** | Restores `shot_clock_remaining` from saved doc. | ✅ Persistence only. |
| **api.py (call-timeout reconciliation)** | Uses `min(backend, displayed, effective_time)` for timeout save. | ✅ Doc §177–194; reconciliation only. |

### 2.2 Where shot clock is read (for contract / response)

| Location | What it does | Doc‑aligned? |
|----------|----------------|-------------|
| **turn_manager._attach_clock_contract** | Reads `game_state["shot_clock_remaining"]` as `sc_end`; writes `shot_clock_start`, `shot_clock_end` onto result. | ✅ Contract reflects current state. |
| **turn_manager.update_clock_and_possession** | `_cc_sc_start = game_state.get("shot_clock_remaining", 30)` at **start** of function; uses it for derived `raw_shot_end` and for contract. | ✅ Next turn’s start = previous turn’s post-reset state. |
| **game_manager (SIP, foul-after-DREB, etc.)** | Passes `shot_clock_start=int(self.game_state.get("shot_clock_remaining", 30))` into `_attach_clock_contract` for bypass/SIP turns. | ✅ Uses current game_state. |

### 2.3 API response (simulate-turn)

- **Top-level:** `shot_clock_remaining` = `gm.game_state.get("shot_clock_remaining", min(30, time_remaining))`.
- **Contract on response:** `shot_clock_start`, `shot_clock_end` from `latest_turn` (or first sub-turn when BATCH).
- So the response **does** send both “current” shot clock and per-turn contract. Frontend **can** rely on it.

### 2.4 Gaps / risks (backend)

1. **BATCH responses:** Top-level `shot_clock_remaining` is from `game_state` **after** the whole batch (FOUL + SIP). So it should already be 30. First sub-turn contract is from FOUL (start/end); second is SIP. So after batch, `turnData.shot_clock_remaining` should be 30 for the **next** request. No gap if game_manager’s “after SIP” set runs.
2. **Single place for “after SIP”:** Right now both turn_manager (reset on FOUL) and game_manager (explicit after SIP) can set 30. Doc says “reset only affects next turn” and lists “defensive foul” as reset instance. Having game_manager set it again after SIP is redundant but safe; keeps next HCO correct even if FOUL path were wrong.
3. **main.py one-offs:** Should be audited so any direct sets use same rule (min(30, time_remaining)) and don’t bypass the normal flow.

---

## 3. Frontend audit

### 3.1 Where shot clock is set (display)

| Location | What it does | Doc‑aligned? |
|----------|----------------|-------------|
| **gameScene.updateScoreboard (shot block)** | (1) If `result_type === 'SIDE_INBOUND'` → sync to **30**. (2) Else if no-impact and `shouldResetShotClockOnTurn` → sync to **30**. (3) Else if `incomingShotSec !== null` → sync to that. (4) Else if `shouldResetShotClockOnTurn` → sync to **30**. | ❌ Re-implements reset and SIP→30. Doc: “reset and shot-clock violation remain backend-only”; frontend should use turn’s `shot_clock_remaining` or `shot_clock_end`. |
| **gameScene (incomingShotSec)** | `incomingShotSec` = `turn.shot_clock_remaining ?? shot_clock_end ?? …`. | ✅ Uses turn/contract when present, but then overridden by (1)(2)(4) above. |
| **AnimationRouter.processTurn** | No-impact: `syncToThirty: isNoImpactTurn` → sync shot clock to **30**. Turn start: sync to `shotClockStart` from turn (or 30). Tween: interpolate `shotClockStart` → `shotClockEnd`. | ⚠️ No-impact branch forces 30 instead of using contract; turn start correctly uses contract. |
| **AnimationRouter (tween onComplete)** | Tween drives display during turn; end value is contract’s end. | ✅ Uses backend contract. |
| **mergeClockContract** | Copies `shot_clock_start`, `shot_clock_end`, etc. from `turnData` (response) onto `turn`. | ✅ So turn has backend contract; but updateScoreboard still has its own rules. |

### 3.2 Post-batch / summary updates

- After batch or loop, `updateScoreboard({ home_score, away_score, clock, ... })` is called **without** `shot_clock_remaining` or `result_type`. So `incomingShotSec` is null and `shouldResetShotClockOnTurn(turn)` is false → shot clock display is **not** updated there. That’s correct only if we already set it when processing the last sub-turn (SIP). So reliance on “SIP → 30” in updateScoreboard is why we don’t see 24 after batch; doc would say we should instead use the **response’s** `shot_clock_remaining` (which backend sets to 30 after batch).

### 3.3 Gaps (frontend)

1. **Duplicate reset logic:** `shouldResetShotClockOnTurn` and explicit SIDE_INBOUND / no-impact branches duplicate backend rules. Doc: frontend should use “turn’s explicit field when present (`shot_clock_remaining`), else use the contract end value **`shot_clock_end`**” and not implement reset.
2. **Hardcoded 30:** SIDE_INBOUND and no-impact branches use `syncWithBackend(30)`; doc says cap when game clock < 30 (backend sends that); frontend should use the value from the response, not 30.
3. **Two writers:** updateScoreboard and AnimationRouter both set shot clock; AnimationRouter correctly uses contract for turn start and tween; updateScoreboard overrides with its own rules. So “single source of truth” is broken on the client.

---

## 4. Work plan (SS&S: backend authority, frontend dumb display)

### Phase A: Backend (ensure every response is authoritative)

1. **Confirm single pipeline for “after SIP”**  
   - Keep game_manager’s explicit `shot_clock_remaining = min(30, time_remaining)` after appending SIP.  
   - Ensure no path creates the next HCO without this state (e.g. no reload from DB that lacks this field).

2. **Ensure response always carries current shot clock**  
   - Already: top-level `shot_clock_remaining` and per-turn contract.  
   - For BATCH: top-level is post-batch state (correct).  
   - Optional: add `shot_clock_remaining` to each sub-turn in batch if frontend will consume per-sub-turn; otherwise frontend can use top-level after processing last sub-turn.

3. **Audit main.py**  
   - Any direct `game_state["shot_clock_remaining"] = …` should use `min(30, time_remaining)` and be justified (e.g. quarter init, special flow). No ad-hoc values.

4. **Tests**  
   - After D_FOUL → SIP (batch), next request returns HCO with `shot_clock_start` = 30 (or min(30, time_remaining)).  
   - After offensive foul → SIP, same.  
   - When `time_remaining` < 30, shot_clock_remaining in response ≤ time_remaining.

### Phase B: Frontend (dumb display only)

1. **Single rule in updateScoreboard**  
   - Compute one value: `turn.shot_clock_remaining ?? turn.shot_clock_end ?? turnData.shot_clock_remaining` (with fallback only when absent; log if fallback used).  
   - If that value is a number (and in 0–30), `this.shotClock.syncWithBackend(value)`.  
   - **Remove:** all branches that sync to 30 based on `result_type`, `shouldResetShotClockOnTurn`, or no-impact. Remove `shouldResetShotClockOnTurn` and the SIDE_INBOUND / no-impact shot-clock branches.

2. **When turn is missing (e.g. post-batch summary)**  
   - If `updateScoreboard` is called with only `{ home_score, away_score, clock }`, use `turnData.shot_clock_remaining` from the **last** response if available (e.g. store it on scene or pass it in). If not available, do not change shot clock (or use explicit “response snapshot” passed after batch). So: after a batch, the response’s top-level `shot_clock_remaining` must be used once when applying “post-batch” state.

3. **AnimationRouter**  
   - Turn start: keep syncing to `shot_clock_start` from contract (already correct).  
   - No-impact: **remove** `syncToThirty: isNoImpactTurn`; instead sync to the turn’s `shot_clock_start` / `shot_clock_end` (they should be 30 or capped from backend). So no frontend “reset to 30” in AnimationRouter.

4. **Pause behavior**  
   - Keep pausing shot clock for no-impact turns (so countdown doesn’t run); only the **value** displayed should come from backend, not the decision to show 30.

5. **Tests / manual**  
   - D_FOUL → SIP → HCO: shot clock shows 24 (or FOUL end) → 30 (SIP) → 30 counting down (HCO start).  
   - Offensive foul / dead ball → SIP: same pattern.  
   - End of quarter: shot clock never above game clock.

### Phase C: Cleanup and doc

1. Remove dead code: `shouldResetShotClockOnTurn`, `isNoImpactShotClockTurn` (if only used for shot reset logic; keep if still used for pause).  
2. Update `Real_Time_Clock_System.md` §101–102 if needed to explicitly say: “Frontend uses only `shot_clock_remaining` or `shot_clock_end` from the response/turn; it does not implement reset or SIP→30.”  
3. Add a short “Shot clock authority” note in this doc or the main clock doc: backend sets and sends; frontend displays.

---

## 5. Summary

| Layer | Current | Target |
|-------|--------|--------|
| **Backend** | Sets shot clock in turn_manager (contract then reset) and game_manager (after SIP); response includes `shot_clock_remaining` and contract. | Keep; ensure BATCH and next-request state are correct; audit main.py; add tests. |
| **Frontend** | updateScoreboard implements reset/SIP→30 and no-impact→30; AnimationRouter syncs to 30 on no-impact. | Use only backend-sent values; one branch: value from turn/response → sync; remove all “reset” and “30” logic. |

**Result:** Backend remains the only place that applies shot clock rules; frontend only displays what the backend sends. Doc §101–102 is then satisfied and the “mickey mouse” duplicate logic is removed.
