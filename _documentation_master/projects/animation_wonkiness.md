

##Main Buckets of Animation Issues

**Unusually Long Pauses in HCO steps**
- Desired behavior, no pauses between HCO steps unless intentionally coded
- This seems to be exclusive to Motion offense
- This does not happen all steps, but in many
- All ten players remain frozen or stationary for unusually long beats

- Desired behavior
    - We eliminate unnecessary pauses between steps when they're not dictated by a bh hold
    - If a bh hold is in palce that should not preclude the other 9 players form moving. I don't know if htis is the case, but we should find out.
    - While we should not have steps where all ten players are programmed to be stationary, but if we should consider an idle organic movment animation for palyer sprite on steps where they are stationary

**Pause Between Some Turn Transitions**
- Desired Behavior: no pause between turns unless specificaly coded
- We may have some pauses programemd for soem reason and others may be due to buggy animation. We need to research.
- Transitions where I'm consistently seeing pauses
    - DREB to HCO
    - DREB to FB
    - HCT (steal) to FB

- For comparison, turn transistion that are no pause perfect every time
    - HCO to SIP (after a foul or db turnover)
    - HCO shot (make or miss) to DREB or OREB
    - HCO make to BIP
    - HCO (steal) to HCO (new team offense)
    - SIP to HCO
    - FCP (steal) to HCO
    - HCT (foul) to SIP
    - HCT (foul) to Free Throw
    - HCT to HCO


**Pause Between Some Step Transitions**
- Desired Behavior: no pause between steps unless specficially coded
- We may have some pauses programemd for soem reason and others may be due to buggy animation. We need to research.
- Transitions where I'm consistently seeing pauses
    - RR & Triangl FB -- the Outlet REceiver passing to the RR down court

**Defense Movment Relative to Pass Animation in HCO turns**
- desired behavior: the ball detaches from teh passer at the same time tha tthe defenders begin moving ot their step destinations, so these movements should be in unison.
- bug: in some, but not all steps with a pass, the defenders are moving to their position, then the ball detaches from teh passr to the receiver
- Situtaions where I"m definitley seeing this consistentlh
    - Set Play vs Zone Defense (many if not all instances)
    - Motion offense vs Zone Defense (some if not many instances)
    - Motion Offense vs Man Defense (some if not many instances)
    - Set Play vs Man Defense (some if not many instances)

---

# Analysis (2026-06-30)

## The meta-insight first (why prior fixes failed)

Both dynamic-HCO flags are **ON** (`.env.local:12-13`), which routes Motion and Set-Play through the **backend-authored schema engine** (`animationPlayback.js`) — the FE is a *pure renderer*. **Three of the four buckets are wholly or partly authored in the Python emitters**, not the JS. The pause durations are literally stamped into the step payload (`time_elapsed`, `hold_ms`) and the frontend faithfully renders them. That's almost certainly why round after round of frontend-only agent fixes bounced off — they were tuning the renderer while the numbers come from the backend.

So: this is **engineering, not a Claude Design task.** Claude Design would only be relevant to one *sub-idea* (idle-sprite organic movement art in Bucket 1). Everything else is game-engine timing logic across the Python emitters + two JS playback engines.

---

## Bucket 1 — Long pauses between HCO steps (Motion only)

**Root cause: backend-stamped step duration, not a render bug.** Motion emits "subtle-movement" beats with a per-step floor of **2–4 game-seconds** (`SUBTLE_STEP_ELAPSED_BY_TEMPO`, `motion_step_decision.py:39-41`), stamped into `step.end.time_elapsed` via `skeleton_step_emitter.py:1592-1593`. Ordinary HCO/Set-Play steps use a 0.5s floor. The schema engine then **hard-waits the full amount** regardless of whether anyone moves (`animationPlayback.js:781-786` and the `await waitMsRespectingPause` at `:1004`). At 350ms/game-sec that's **700–1400ms of all-ten-frozen** per subtle beat, and since subtle beats barely move anyone, natural travel time never masks it. Set Play forces `offense_reads=False`, so it emits far fewer subtle beats → no pauses. That's the Motion-exclusivity.

**Fix direction (recommended):** decouple *clock consumed* from *visual time*. Keep 2–4s on the sim ledger for pacing, but stamp a small visual `time_elapsed`. Optionally (Bucket-1 secondary desire) give the 9 off-ball players real drift during the beat so it reads as motion, not a freeze — that off-ball-drift piece is the one place a design sensibility helps.

## Bucket 2 — Pauses between turn transitions (DREB→HCO, DREB→FB, HCT-steal→FB)

**Root cause: a hardcoded `hold_ms: 1000` announcement stamped at the boundary, awaited inline.** DREB emits `"Rebound!"` with `hold_ms:1000` **unconditionally** (`dreb_step_emitter.py:220-227`); the steal→FB drive emits `"Fast Break!"` with `FB_ANNOUNCE_HOLD_MS=1000` on step *start* (`after_steal_fast_break_step_emitter.py:58,174`). The engine blocks on both via `await waitMsRespectingPause(scene, holdMs)` (`animationPlayback.js:743`). The "clean" transitions are clean for concrete reasons: steal→HCO/HCT/FCP gets a *silent* bridging step (`_append_post_steal_hco_transition`) that is explicitly a **no-op for steal→FAST_BREAK**; and shot→DREB shows the same 1000ms as the rebound *moment* so it reads as intentional. Also note: the old DREB→HCO outlet lead-in that used to fill this window was removed (`AnimationEngine.js:366-374`), leaving the hold bare — and the Unified doc still describes it as live (stale docs).

**Fix direction:** make the boundary hold conditional on `next_play_type` (zero it for live continuations, keep for dead-ball), or add a `non_blocking` announcement flag so the overlay shows while play continues.

## Bucket 3 — Step pause in RR / Triangle FB (outlet → rim-runner pass)

**Root cause: a frontend await-barrier** (this one *is* pure FE — fastBreak.js is the unmigrated legacy engine). After the outlet pass lands, the phase does `await Promise.all(secondary)` (`fastBreak.js:2364-2367`, Triangle equiv at `:883`) — where `secondary` includes the rim runner's long sprint tween. The receiver already holds the ball; everything visible is static except the RR finishing his glide, and the lane pass is blocked behind that barrier → dead air. There's a ready-made escape hatch (`isCriticalEventPatternEnabled()`) that kills the barrier, but it's **defaulted off** pending an unrelated `animateDefensiveStop` hang (`fastBreak.js:173-180`).

**Fix direction:** don't put the RR tween in the awaited `secondary` set (let the lane pass spawn a fresh RR catch tween from live position, which it already does), or clamp the RR burst duration so it can't outlast the outlet beat.

## Bucket 4 — Defenders move before the ball detaches (HCO passes)

**This one needs a caveat — the mechanism found is in the *legacy* engine, but the live path is the schema engine.** In legacy `turnAnimation.js` the bug is real and clear: pass-step defenders are deferred, the step `await passerPromise`s, and defenders are started *before* the ball detaches through a chain of `await import()` ticks (`turnAnimation.js:4868-4890, 4897-4901, 5060-5091`). Zone + Set-Play amplify it (bigger defender reposition tweens, real passer pre-movement).

**But** the live Motion/Set-Play schema engine appears to already do this correctly: player tweens (incl. defenders) and the ball transition start in one synchronous block (`animationPlayback.js:922-956`), and the pass-step code explicitly comments *"release at step start in parallel with all player tweens (passer, receivers, defenders)"* (`animationPlayback.js:304-315`). So either (a) the desync seen is on HCO branches that *don't* emit `animation_steps` and fall back to the legacy engine, or (b) there's a subtler timing detail inside `renderBallTransition`. **This is the one bucket that can't be fully closed from static tracing** — it needs a runtime check: add a trace to confirm which engine renders a Set-Play-vs-Zone pass step that visibly desyncs.

---

## How I'd sequence this

| # | Bucket | Where the fix lives | Confidence | Effort |
|---|--------|--------------------|-----------|--------|
| 1 | Turn-transition pauses | Backend emitters (2 files) | **High** | Low — start here, biggest win/effort |
| 2 | HCO step pauses (Motion) | Backend (clock/visual split) | **High** | Medium |
| 3 | RR/Triangle FB step pause | Frontend fastBreak.js | **High** | Low–Med |
| 4 | Defender/ball desync | Needs engine confirmation first | **Medium** | Investigate before fixing |

Recommended order: knock out **Bucket 2 first** (two conditional `hold_ms` edits, immediately visible), then **Bucket 3**, then **Bucket 1** (the clock-vs-visual split is the meatiest but well-understood), and treat **Bucket 4** as investigate-then-fix rather than assuming the legacy-engine patch applies.
