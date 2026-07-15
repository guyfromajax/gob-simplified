# FCP / HCT ↔ UESS Compliance Audit

**Date:** 2026-07-04 · **Scope:** Dynamic FCP/HCT turns (shared `compute_dynamic_hct_turn` loop + `dynamic_hct_step_emitter`) · **Method:** read-only trace from live bug report + prior interception animation analysis · **Result of audit only — no code changed for this entry.**

---

## ⭐ TL;DR (human topline — read this first)

**Reported bug:** FCP turn → pass intercepted → “INTERCEPTION!” SFX played once → then **infinite ball-landing / receive SFX** with **frozen court** and **no game progression** until page refresh (Mid Game Resume).

**What the code definitely shows (high confidence):**

| Symptom / gap | Root cause | Verdict |
|---|---|---|
| Interception announced but no pass flight to interceptor | Backend `INTERCEPT` used to emit `_emit_stopper("hct_interception")` only. **Updated 2026-07-15:** the engine now stamps interception metadata and the shared HCT/FCP emitter projects a real pass-flight-to-stealer schema step. | ✅ **Fixed in schema path** |
| Ball may stay on passer through stopper; stealer gets ball only on post-steal step (teleport) | Stopper path used to keep `ball.owner = passer`; post-steal transition set `ball.owner = stealer_id` later. **Updated 2026-07-15:** `hct_interception` step now ends with `ball.owner_player_id = stealer_id` before post-steal transition. | ✅ **Fixed in schema path** |
| Schema STEAL turn_stop does nothing useful | `dispatchTurnStop` → `runSteal` used to be a stub. **Updated 2026-07-15:** schema `runSteal` now performs cleanup-only ball ownership finalization without replaying legacy steal animation or duplicate announcements. | ✅ **Fixed in schema path** |
| Infinite receive / ball-landing SFX loop | **Not pinned to a single wiring bug** in the interception path; would require `playTurn` re-running pass steps or runtime evidence | ⚠️ **Unconfirmed — needs repro dump** |

**Current next fix direction:** move pressure builders upstream to produce formal PressureStepState first. Pass-interception flight, schema terminal cleanup, batted-OOB ball flight, TurnManager pressure emission, additive pressure StepState stamping, and a parity-tested StepState projection bridge are now aligned for the dynamic schema path.

---

## Issue: FCP pass interception — frozen turn + repeating ball-landing SFX

### User report (2026-07-04)

- Turn type: **FCP** (dynamic, `animation_steps` path).
- Outcome: **pass interception** (`is_interception: true`, `result_type: STEAL`).
- **Interception SFX** sounded (likely turn-end `finalizeTurnAfterAnimation` → `announceGameEvent('STEAL')` with `isPassInterception`).
- Then: **repeating ball-landing / receive SFX**, **no player movement**, **turn never completes** until refresh + Mid Game Resume.

### Backend path (confirmed)

**File:** `BackEnd/engine/dynamic_hct.py` (FCP delegates via `dynamic_fcp.py` → `turn_mode="fcp"`).

On pass decision, `_resolve_hct_pass_contest` runs **before** any pass segment is appended:

```
pass decision → contest outcome INTERCEPT
  → result_type = STEAL, is_interception = True, stealer = interceptor
  → _emit_stopper("hct_interception", ...)
  → stamp pass_from_pos / pass_to_pos / interceptor_pos / interception_contact
  → break
```

`_emit_stopper` appends the terminal loop segment; the stamped metadata lets the emitter project it as a pass-interception step rather than a generic stopper.

**Turn assembly:** `BackEnd/engine/phase_resolution.py` → `_resolve_full_court_press_dynamic_first_cut` sets `stealer_id`, `is_interception`, `fcp_loop_segments`, etc.

### Emitter path (confirmed)

**File:** `BackEnd/engine/dynamic_hct_step_emitter.py` (FCP wrapper: `dynamic_fcp_step_emitter.py`).

| Segment reason | Step builder | Pass SFX? |
|---|---|---|
| `hct_pass` | `build_pass_step` | Yes (`sfx_on_ball_arrival`) |
| `hct_interception` | `_build_interception_pass_step` | Yes (`sfx_on_ball_arrival`) |

Last segment gets `end.next = turn_stop STEAL` via `_resolve_final_step_next`, unless the existing post-steal transition rewires it to the transition step.

If `next_play_type ∈ {HCO, HCT, FCP}`, `skeleton_step_emitter._append_post_steal_hco_transition`:
- Rewires stopper `next` → post-steal step index.
- Post-steal step: starts after the interception step already ended with ball `owner_player_id = stealer_id`; players reposition; **turn_stop STEAL** moves to post-steal step end.

**Reference implementation (what FCP/HCT lacks):** `BackEnd/engine/rim_runner_step_emitter.py` → `_build_lane_pass_intercepted_step` — BH passes, stealer sprints to contact grid, ball `attached(BH) → attached(stealer)`, `ball_reaches_player` gate, step-end “Interception!” announcement.

### Frontend path (confirmed)

**Routing:** `animateGameTurns.js` → STEAL with `animation_steps` → `AnimationRouter.processTurn` → `AnimationEngine.processTurn` → **`runSchemaPlaybackTurn`** (early return; **does not** call `handleSteal`).

**Playback:** `animationPlayback.js`
- `playTurn` walks steps; stops at first `turn_stop`.
- `dispatchTurnStop` → `runSteal` cleanup-only handler.
- `runSteal` does not animate or announce. It clears stale pass/pending-owner state and aligns BallController / legacy ball holder / visible ball attachment to the backend-authored stealer.

**Announcements / SFX:**
- Interception voice: `turnPreparation.finalizeTurnAfterAnimation` → `gameAnnouncements` STEAL handler → `isPassInterception(turn)` → “INTERCEPTION!” + `resolveInterceptionSfxFile()` (**once**, at turn end).
- Receive / ball-landing: `receive-*.wav` via `sfx_on_ball_arrival` on **`build_pass_step`** only — fired once per pass step at ball tween complete (or step-end fallback if ball doesn’t move).

**Legacy path NOT taken for dynamic FCP:** `AnimationEngine.handleSteal` attaches ball to stealer after skeleton — skipped when `animation_steps` present.

### Infinite SFX loop — what we could / could not prove

**Could not confirm** a single interception-specific `next` pointer cycle. Expected chain is linear: `… → stopper → post_steal → turn_stop STEAL`.

**Receive SFX repeating** implies either:
1. `playTurn` re-executing **pass steps** from earlier in the same turn (each completion = one receive sound), or
2. Something outside schema playback calling receive SFX in a loop (not traced to a clear source).

`playTurn` throws after **200 steps** if cycling: `playTurn: exceeded 200 steps — likely a cycle in next pointers`.

**Not ruled out without repro:** stuck `await` inside a step, `stealer_id` missing from coords causing post-steal append to no-op, or user-perceived “landing” sound being a different cue than `receive-*.wav`.

---

## Debugging checklist (next agent)

Capture on repro **before** refresh:

1. **Console**
   - unexpected `dispatchTurnStop` terminal-handler warnings
   - `[UESS PLAYBACK] schema:enter` / `schema:exit` (did `playTurn` finish?)
   - `playTurn: exceeded 200 steps` (cycle?)
   - Repeated `pass:release` or `step:post-wait` traces with same `stepId`

2. **Turn JSON** (stuck FCP turn)
   - `result_type`, `is_interception`, `stealer_id`, `victim_id`, `next_play_type`
   - Full `animation_steps[]`: count, last 2–3 steps’ `start.advance_trigger.metadata.reason`, `end.next`
   - Any **`hct_pass`** steps before final segment; verify `end.next` indices don’t point backward

3. **Ball state at freeze**
   - `BallController.getState()` — `currentOwner`, `isAttached`, `isInFlight`, `pendingOwner`
   - Visual: ball on passer vs interceptor sprite

4. **SFX identity**
   - Network/audio tab: is repeating file `receive-*.wav`, `click-steal.wav`, or interception MP3?

---

## Related work already in repo (same family)

| Topic | Status | Notes |
|---|---|---|
| Interception animation (no pass flight) | **Fixed** | `hct_interception` now emits pass flight to stealer/contact point |
| `runSteal` schema stub | **Fixed** | cleanup-only finalization in `animationPlayback.js` |
| HCT/FCP batted-OOB imperative ball-send | **Fixed** | dynamic schema emits contact + OOB drift; frontend imperative helper is fallback only |
| HCT/FCP pressure StepState shape | **Implemented additively** | `pressure_step_state.py` freezes emitted schema into `result["pressure_step_states"]`; no consumer reads it yet |
| HCT/FCP PressureStepState projection | **Started** | `project_pressure_step_states_to_animation_steps` round-trips current schema through StepState with parity tests |
| Defensive mid-court recovery (stranded defenders) | **Implemented** | `_recover_defense_targets` in `dynamic_hct.py` |
| Off-ball x=50 back-movement gate | **Implemented** | `gate_offense_backcourt_reentry` in `over_and_back.py` |
| Rim Runner lane pass intercept | **Reference** | `_build_lane_pass_intercepted_step` |

**Docs:** `FCP_System.md` (over-and-back + defensive recovery); `Z-Completed/Dynamic_FCP_Brief.md`; `Step_By_Step_System.md`.

---

## Remaining fix plan

1. **Upstream PressureStepState builders:** Convert the remaining pressure-turn segment model into formal `PressureStepState` before projection. The projection bridge exists; the next step is moving `_build_loop_step`, pass, interception, batted-OOB, and HCT shot paths to create StepState directly.
2. **Manual repro:** Validate FCP/HCT pass interception, terminal fouls/dead balls, and batted-OOB in-browser.

---

## Key files

| Layer | Path |
|---|---|
| Engine loop | `BackEnd/engine/dynamic_hct.py` |
| FCP entry | `BackEnd/engine/dynamic_fcp.py`, `phase_resolution.py` (`_resolve_full_court_press_dynamic_first_cut`) |
| Step emitter | `BackEnd/engine/dynamic_hct_step_emitter.py`, `dynamic_fcp_step_emitter.py` |
| Post-steal chain | `BackEnd/engine/skeleton_step_emitter.py` (`_append_post_steal_hco_transition`) |
| Intercept reference | `BackEnd/engine/rim_runner_step_emitter.py` (`_build_lane_pass_intercepted_step`) |
| Pass primitive | `BackEnd/utils/transition_bridge.py` (`build_pass_step`) |
| Schema playback | `FrontEnd/static/js/phaser/animation/animationPlayback.js` |
| Turn orchestration | `FrontEnd/static/js/phaser/animation/AnimationEngine.js`, `AnimationRouter.js`, `animateGameTurns.js` |
| Announce / finalize | `FrontEnd/static/js/phaser/animation/turnPreparation.js`, `gameAnnouncements.js` |
