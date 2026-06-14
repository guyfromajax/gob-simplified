# Transition Systems — Hold Times and Delay Reference

> **Hybrid-layer doc:** most of these holds run inside legacy handler paths (`ShotAnimationSystem`, `fastBreak.js`, `ballManager.js`, `turnAnimation.js`). They are presentation-layer pauses (no gameplay logic), so they remain frontend config even under UESS, but the call sites will shrink as turns migrate to schema playback.

## Summary

The transition system controls every **hold and delay** at turn boundaries (shot→rim, rebound attach, inbound, fast break, free throw) so pauses feel consistent and tunable without touching call sites. All values are **centralized** in **`FrontEnd/static/js/phaser/animation/animation_config.js`** and read via `animationConfig.*`; optional overrides can be applied via `globalThis.animation_config`.

**Announcement-related holds** are fixed at **1000 ms** so result text ("It's Good!", FT make, FB make, ballManager made shot) stays readable — except the FB **"Great Stop!"** hold, which was tuned down to **500 ms**. In **ShotAnimationSystem** (HCO made shots), the rim hold and "It's Good!" / AND-1 run **in unison**: one 1000 ms period with the ball at the rim and the announcement visible together, then cleanup (terminal quarter-end shots skip this hold entirely). Other paths use a 1000 ms hold after the announcement. **Non-announcement** delays have been tuned for shorter perceived pauses: shot rim hold 1000 ms (putback/miss path), rebound attach **500 ms**. Fast break rim hold is 1000 ms (makes); FB misses use the rebound flow.

**BIP (baseline inbound) responsiveness update (May 2026):** `inboundHoldMs` 2 × 200 ms holds before the BIP pass are **removed** in `runInboundSetup`; the BIP pass itself runs at **250 ms** (down from 500 ms) for a snappy ball-place → fly → receive sequence. SIP path retains the single 200 ms `holdAfterPlaceMs` (sets the visual rhythm for non-time-pressured side inbounds).

To change a value: edit the **`defaults`** object in `animation_config.js` (and optionally overrides). No call-site changes are needed. For the full list of keys, where they run, and which files use them, see the tables below.

---

## Quick reference: config key → value (ms)

| Config key | Value (ms) | When it runs |
|------------|------------|--------------|
| `shot.rimHoldMs` | 1000 | Ball at rim (putback makes only in ShotAnimationSystem; else runs **in unison** with announcement). |
| `shot.makeAnnouncementHoldMs` | 1000 | **In unison** with rim hold for makes: one 1000 ms period with ball at rim + "It's Good!" / AND-1. |
| `shot.madeRimHoldMs` | 1000 | Made shot rim hold in ballManager path (announcement). **Make only.** |
| `fastBreak.rimHoldMs` | 1000 | Ball at rim after **fast break make**. FB misses use rebound flow (no separate rim hold). |
| `fastBreak.makeAnnouncementHoldMs` | 1000 | After "It's Good!" on FB make. **Make only.** |
| `fastBreak.defensiveStopHoldMs` | 500 | After "Great Stop!" on FB defensive stop. (Call sites fall back to `?? 1000` if the key is absent, but the config default is 500.) |
| `rebound.attachDelayMs` | 500 | After rebounder reaches spot, before ball attach (possession secured). **Miss/block.** |
| `offensiveRebound.pauseMs` | 1000 | Pause before kickout or putback (OREB). |
| `inbound.holdAfterPlaceMs` | 200 | Hold after ball placed with inbound passer. **SIP only** — single application. **BIP path no longer uses this hold** (removed in May 2026 BIP responsiveness update). |
| `freeThrow.rimHoldMs` | 300 | Legacy free throw path (e.g. pre-shot hold). |
| `freeThrow.makeRimHoldMs` | 1000 | Made FT at rim (non-final); announcement hold. **Make only.** |

---

## By context (make vs miss)

**Shot (HCO)**  
- **Make (ShotAnimationSystem):** Rim hold and "It's Good!" / AND-1 run **in unison**: announcement and ball at rim for one period (`shot.makeAnnouncementHoldMs`, 1000 ms), then cleanup.  
- **Make (ballManager path):** `shot.madeRimHoldMs` (1000 ms).  
- **Miss:** Rim hold `shot.rimHoldMs` then rebound.  
- **Putback make:** Rim hold only (`shot.rimHoldMs` or `fastBreak.rimHoldMs`) — no announcement in this path.

**Fast break**  
- **Make:** Ball at rim → `fastBreak.rimHoldMs` (1000 ms). Then "It's Good!" → `fastBreak.makeAnnouncementHoldMs` (1000 ms).  
- **Miss:** No separate FB rim hold; rebound flow uses `rebound.attachDelayMs`.

**Rebound (miss/block)**  
- `rebound.attachDelayMs` (500 ms) — after rebounder reaches spot.  
- OREB: `offensiveRebound.pauseMs` (1000 ms) before kickout/putback.

**Inbound**
- **SIP** (side inbound): `inbound.holdAfterPlaceMs` (200 ms) once after ball placed with passer.
- **BIP** (baseline inbound): no post-placement hold; BIP-pass duration hardcoded to 250 ms in `runInboundSetup` for snappy responsiveness leading into HCO/HCT/FCP.

**Free throw**  
- Legacy: `freeThrow.rimHoldMs` (300 ms).  
- Made FT (non-final): `freeThrow.makeRimHoldMs` (1000 ms).

---

## Where each key is used in code

| Config key | File(s) |
|------------|--------|
| `shot.rimHoldMs` | `ShotAnimationSystem.js` (HCO rim hold) |
| `shot.makeAnnouncementHoldMs` | `ShotAnimationSystem.js` (after "It's Good!" / AND-1) |
| `shot.madeRimHoldMs` | `ballManager.js` (made shot rim hold) |
| `fastBreak.rimHoldMs` | `ShotAnimationSystem.js` (FB make rim hold) |
| `fastBreak.makeAnnouncementHoldMs` | `fastBreak.js` (after FB "It's Good!") |
| `fastBreak.defensiveStopHoldMs` | `fastBreak.js` (after "Great Stop!") |
| `rebound.attachDelayMs` | `ballManager.js` (animateRebound) |
| `offensiveRebound.pauseMs` | `turnAnimation.js` (OREB pause before kickout/putback) |
| `inbound.holdAfterPlaceMs` | `turnAnimation.js` (SIP only — `runSideInboundSetup`, after SF receives ball) |
| `freeThrow.rimHoldMs` | `freeThrow.js` (legacy path) |
| `freeThrow.makeRimHoldMs` | `FreeThrowAnimationSystem.js` (made FT at rim) |

---

## Changing a value

1. Open **`FrontEnd/static/js/phaser/animation/animation_config.js`**.  
2. Update the **`defaults`** object (e.g. `defaults.shot.rimHoldMs = 600`).  
3. Optional: support overrides via `globalThis.animation_config` (already wired for some keys).  
4. No need to change call sites; they read from `animationConfig` with fallbacks (e.g. `?? 1000`).  

For announcement-related holds (1000 ms), see **`../05_GP_Supporting_Systems/Announcement_System.md`** (uniform 1000 ms rule).
