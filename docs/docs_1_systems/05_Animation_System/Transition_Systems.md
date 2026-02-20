# Transition Systems — Hold Times and Delay Reference

This doc lists all config-driven **hold times and delays** that affect turn transitions and announcement display. Use it to request tweaks (e.g. "set shot rim hold to 600 ms" or "reduce rebound attach to 400 ms"). All values live in **`FrontEnd/static/js/phaser/animation/animation_config.js`**; code reads them via `animationConfig.*`.

---

## Quick reference: config key → value (ms)

| Config key | Value (ms) | When it runs |
|------------|------------|--------------|
| `shot.rimHoldMs` | 1000 | Ball at rim after **make or miss** (HCO); same duration for both. |
| `shot.makeAnnouncementHoldMs` | 1000 | After "It's Good!" / AND-1, before inbound. **Make only.** |
| `shot.madeRimHoldMs` | 1000 | Made shot rim hold in ballManager path (announcement). **Make only.** |
| `fastBreak.rimHoldMs` | 1000 | Ball at rim after **fast break make**. FB misses use rebound flow (no separate rim hold). |
| `fastBreak.makeAnnouncementHoldMs` | 1000 | After "It's Good!" on FB make. **Make only.** |
| `fastBreak.defensiveStopHoldMs` | 1000 | After "Great Stop!" on FB defensive stop. |
| `rebound.attachDelayMs` | 500 | After rebounder reaches spot, before ball attach (possession secured). **Miss/block.** |
| `offensiveRebound.pauseMs` | 1000 | Pause before kickout or putback (OREB). |
| `inbound.holdAfterPlaceMs` | 200 | Hold after ball placed with inbound passer (SIP/BIP); applied **twice** in sequence. |
| `freeThrow.rimHoldMs` | 300 | Legacy free throw path (e.g. pre-shot hold). |
| `freeThrow.makeRimHoldMs` | 1000 | Made FT at rim (non-final); announcement hold. **Make only.** |

---

## By context (make vs miss)

**Shot (HCO)**  
- **Make and miss:** Same rim hold → `shot.rimHoldMs` (1000 ms). Ball at rim, then make path does announcement + `shot.makeAnnouncementHoldMs`; miss path goes to rebound.  
- **Make-only (ballManager path):** `shot.madeRimHoldMs` (1000 ms).

**Fast break**  
- **Make:** Ball at rim → `fastBreak.rimHoldMs` (1000 ms). Then "It's Good!" → `fastBreak.makeAnnouncementHoldMs` (1000 ms).  
- **Miss:** No separate FB rim hold; rebound flow uses `rebound.attachDelayMs`.

**Rebound (miss/block)**  
- `rebound.attachDelayMs` (500 ms) — after rebounder reaches spot.  
- OREB: `offensiveRebound.pauseMs` (1000 ms) before kickout/putback.

**Inbound (SIP/BIP)**  
- `inbound.holdAfterPlaceMs` (200 ms), applied twice after ball placed with passer.

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
| `inbound.holdAfterPlaceMs` | `turnAnimation.js` (SIP and BIP, hold after ball placed) |
| `freeThrow.rimHoldMs` | `freeThrow.js` (legacy path) |
| `freeThrow.makeRimHoldMs` | `FreeThrowAnimationSystem.js` (made FT at rim) |

---

## Changing a value

1. Open **`FrontEnd/static/js/phaser/animation/animation_config.js`**.  
2. Update the **`defaults`** object (e.g. `defaults.shot.rimHoldMs = 600`).  
3. Optional: support overrides via `globalThis.animation_config` (already wired for some keys).  
4. No need to change call sites; they read from `animationConfig` with fallbacks (e.g. `?? 1000`).  

For announcement-related holds (1000 ms), see **`docs/docs_1_systems/05_GP_Supporting_Systems/Announcement_System.md`** (uniform 1000 ms rule).
