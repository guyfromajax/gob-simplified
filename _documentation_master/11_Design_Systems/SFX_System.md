# SFX System

Single source of truth for in-game sound: bindings, triggers, variant rules, runtime wiring, and library strategy.

**Related:** [`UESS_System.md`](../00_General_Systems/UESS_System.md) (schema `meta.sfx`, `sfx_on_ball_release` / `sfx_on_ball_arrival`, `timed_sfx` on steps) · [`Announcement_System.md`](../05_GP_Supporting_Systems/Announcement_System.md) (court stingers via announce payload)

**Code:** `FrontEnd/static/js/phaser/utils/gameSfx.js` (preload, pools, playback) · `BackEnd/utils/animation_step_helpers.py` (backend stamps) · `FrontEnd/static/js/phaser/animation/animationPlayback.js` (schema step SFX)

**Supersedes** (archived in `projects/Z-Completed/`): `SFX_System.md`, `SFX_Manager_Implementation.md`, `SFX_Brief.md`

---

## Runtime (implemented)

- **Preload:** gameplay SFX preloaded in `bootGame.js` before `GameScene`.
- **Playback:** all gameplay and court-stinger audio through `playGameSfx()` — small per-file pools, scene-retained until `ended` / `error`. **Exception:** the quarter-break / clock-zero airhorn (`airhorn-lowervol.wav`) plays via raw `new Audio()` in `bootGame.js` and `AnimationEngine.js`.
- **Schema path:** backend stamps `sfx_on_ball_release`, `sfx_on_ball_arrival`, `timed_sfx`, and step `meta.sfx`; FE plays at ball detach/arrival and announce mount (no parallel legacy `Audio()` paths for those events).
- **Announcements:** `meta.sfx` on announce payloads → `court.html` overlay mount → `playGameSfx` (see Court Event SFX below).
- **Debug:** `window.DEBUG_GAME_SFX = true` or `?debug_sfx=1`.
- **Passes 1–2 shipped:** central manager + shot timing markers (`onShotRelease`, `onShotArrive`) on shared shot helpers. Phases 3–7 in the old implementation plan remain aspirational (marker inventory, broader migration).

---

## Bindings and variant rules

## Backend Terms

- `shot_score_pre_defense`: Existing `resolve_shot()` local variable. This is returned from `calculate_shot_score()` as `pre_defense_shot_score` and represents the shooter/offense value before defensive shot impact is applied.
- `shot_score`: Existing final shot score after defensive impact and later modifiers. This remains the make/miss score compared against `shot_threshold`.
- `shot_defense_score_for_sfx`: Existing SFX metadata value that exposes defensive shot impact. Current missed-shot SFX no longer branches on this value, but keep the field available for future sound-selection rules.

## Shot Launch SFX

**All Shot Types (Inside, Attack, Outside)**
- Trigger: at the moment the ball detaches from the shooter sprite.
- Score source: `shot_score_pre_defense`.
- `< 101`: `three-weak.wav`
- `> 210`: `three-strong.wav`
- Else: `shot-standard.wav`
- The `> 210` strong tier also stamps `hot_shot_trail` on the step metadata — FE `renderBallTransition` renders a hot trail on schema `[ball_flight]` steps (same threshold as `three-strong.wav`).

**Blocked Shot Attempts (override)**
- When the shot is blocked (`turnData.result_type === "BLOCK"`), the attempt SFX is `block1.wav` and **takes precedence over the `shot_score_pre_defense` tiers above** — the scale tiers are skipped.
- Checked first in `playShotLaunchSfx` (gameSfx.js). The block result is already known at release time because the backend resolves the full turn before animation.

**Free Throw Shot Attempts**
- All: `shot-standard.wav`

## Gameplay Pass SFX

**Passes**

- Trigger: at the moment the ball detaches from the passer sprite.
- Scope: HCO, HCT, FCP, BIP, SIP, and Fast Break non-outlet passes.
- Exclusion: Fast Break outlet passes use their dedicated outlet SFX and should not also play these pass/reception SFX.
- Passer `PS > 75`: `pass-strong.wav`
- Passer `PS < 25`: `pass-weak.wav`
- Else: `pass-medium.wav`

**Receptions**

- Trigger: at the moment the ball reaches the receiver sprite.
- Scope: HCO, HCT, FCP, BIP, SIP, and Fast Break non-outlet receptions.
- Exclusion: Fast Break outlet receptions use their dedicated outlet SFX path and should not also play these pass/reception SFX.
- Receiver `(IQ + CH) > 130`: `receive-strong.wav`
- Receiver `(IQ + CH) < 50`: `receive-weak.wav`
- Else: `receive-medium.wav`

**Free Throw**

- **Launch** (ball leaves shooter): `shot-standard.wav` — same trigger as other shot types (see Shot Launch SFX).
- **Result** (rim action + SFX): chosen by `shot_variant` on the FT turn (see **Free Throw Makes** / **Free Throw Misses** and **Free Throw SFX bindings**). Not a single swish/miss file at basket arrival for every FT.

**Lower-volume file swaps (shipped):** the code uses the `-lowervol` variants everywhere — `confirm-1-lowervol.wav`, `confirm-2-lowervol.wav`, `whistle-1-lowervol.wav`, `airhorn-lowervol.wav` (originals retired).


## Court Event SFX

Court event stingers cover both the primary center-court overlay and the secondary top-edge ribbon (plus the Defense Matchups modal). All announcement-tied SFX route through the **payload-carries-SFX architecture**:

1. The caller passes `meta.sfx = '<filename>'` (string), an array of filenames, or a legacy kind string (e.g. `'foul'`, `'shot_clock_violation'`, `'fb_outlet_denied_court'`, `'steal'`).
2. The announcement helper (`showAnnouncement` / `showAndOneAnnouncement` / `showSecondaryAnnouncement` in `announcements.js`) resolves the value to a filename via `resolveAnnounceMetaCourtSfxFile` / `resolveSecondaryAnnounceCourtSfxFile` / `resolvePrimarySfxFromMeta` and puts it on the payload as `data.sfx`.
3. `court.html`'s overlay mount functions read `data.sfx` and call `window.playGameSfx(filename)` at the moment the DOM mounts — synced to the visual entry.

Net result: **one dispatch point per tier** (`window.showAnnouncementOverlay` and `window.showSecondaryAnnouncementOverlay`). No JS module outside `gameSfx.js` calls `playFBOutletDeniedCourtSfx` / `playChargeAnnounceCourtSfx` / `playAnnouncementSfx` / etc. directly anymore.

**Shared rules**

- Volume: **0.7** (same as other court SFX). All audio goes through `playGameSfx` (preloaded pool, scene-retained).
- **One SFX per show** — fire once when the UI moment appears; do not stack on re-entrant or idempotent announce calls for the same visible show. Once-per-turn dedupe for `Press!` / `Trap!` / `Fast Break!` is enforced inside `resolveSecondaryAnnounceCourtSfxFile`.
- Assets live under `FrontEnd/static/sounds/`; `playGameSfx` already URL-encodes the filename.

**Whistles (foul / dead-ball / shot clock)**

- Foul or dead-ball turnover announcement shown: `whistle-1-lowervol.wav` (via `meta.sfx` on the announce payload from `gameAnnouncements.js`). Not played for STEAL! (live-ball).
- Shot Clock Violation announcement: `whistle-3.mp3` (legacy kind `shot_clock_violation` in `gameSfx.js`).

**Timeout airhorn**

- Trigger: timeout popup appears (user-called) or computer timeout navigates to lineup.
- File: `airhorn-lowervol.wav` at 0.7 — raw `Audio()` in `timeoutButtonManager.js` (same exception class as the quarter-break/clock-zero airhorn noted in Runtime).

**Defense Matchup Modal**

- Trigger: immediately when the modal **opens** (not on submit or close).
- File: `defense-sammy.mp3`

**Fast Break Announce**

- Trigger: immediately when the **Fast Break!** secondary announce appears.
- File: `fast-break-braddock.mp3`
- Scope: only when that headline is actually shown. No stinger for steal-entry paths that suppress Fast Break announce, and no stinger for other fast-break copy (`FB Outlet Pass Denied!`, `No Fast Break`, `Great Stop!`, etc.) unless the **Fast Break!** ribbon is shown.

**Trap Announce**

- Trigger: immediately when the **Trap!** secondary announce appears.
- File: `trap-braddock.mp3`

**Press Announce**

- Trigger: immediately when the **Press!** secondary announce appears.
- File: **50/50** random each show — `sammy-press.mp3` or `press-braddock.mp3`

**Quick Shot Announce**

- Trigger: immediately when the **Quick Shot** secondary announce appears.
- File: `quick-shot-braddock.mp3`

**Slow It Down Announce**

- Trigger: immediately when the **Slow It Down** secondary announce appears.
- File: `slow-it-down-braddock.mp3`

**Final Shot Announce**

- Trigger: immediately when the **Final Shot** secondary announce appears.
- File: **50/50** random each show — `sammy-final-shot.mp3` or `final-shot-braddock.mp3`

**Block Announce**

- Trigger: immediately when the **Block** announce appears.
- File: `duke-its-blocked.wav`

**Opening Tip SFX**

- Trigger 1: immediately when the jumping players begin to jump (i.e move upward)
- File 1: `attack-shot-medium.wav`

- Trigger 2: immediately when the ball attaches to the player who receives the opneing tip
- File 2: `attack-shot-strong.wav`

**Rebound SFX**
- Trigger for both D and O Rebounds: immediately when the ball attaches to the rebounder sprite
- Defensive Rebound
    - File: `attack-shot-strong.wav`
- Offensive Rebound
    - File: `inside-shot-strong.wav`

**Steal Announce**

- Trigger: immediately when the **STEAL!** Announce appears (reach-in / strip — i.e. NOT a pass interception).
- File: **33/33/34** random each show — `sammy-steal.wav` or `braddock-steal.wav` or `butler-steal.wav`
- Resolver: `resolveStealSfxFile()` (gameSfx.js).

**Interception Announce**

- Trigger: immediately when the **INTERCEPTION!** Announce appears (a PASS interception — Rim Runner lane pass, or the HCT/HCO/FCP pass-contest primitive's INTERCEPT terminal).
- File: **33/33/34** random each show — `braddock-interception.mp3` or `duke-interception.mp3` or `sammy-interception.mp3`
- Resolver: `resolveInterceptionSfxFile()` (gameSfx.js). Legacy `meta.sfx` key: `"interception"`.

**Made Three Announce**

- Trigger: immediately when the **It's Good!** Announce appears for a made 3-pointer (`turnData.points === 3` in `handleShotMakeAnnouncement`, gameAnnouncements.js). 2-pt makes carry no court SFX here; FT makes and 3-pt and-1s are not covered.
- File: **33/33/34** random each show — `braddock-three.mp3` or `duke-three.mp3` or `sammy-three.mp3`
- Resolver: `resolveThreePointerSfxFile()` (gameSfx.js). `meta.sfx` key: `"three_make"` (passed on the "It's Good!" announce payload).

**Airball Announce**

- Trigger: immediately when the **Airball!** Announce appears (`handleAirballAnnouncement`, gameAnnouncements.js).
- File: `airball-emotion.wav` (a reaction stinger), passed directly as `meta.sfx` on the announce payload → plays at overlay mount.
- Note: distinct from `airball.wav`, which fires earlier from the **shot-result** SFX at ball-miss (see Shot Make/Miss). Both play for an airball — the result clank-tier at the miss, the emotion stinger at the announcement.

**Charge Announce**

- Trigger: immediately when the Charge Announce appears.
- File: `duke-charging.wav`

**FB Defensive Stop Announce**

- Trigger: immediately when the Great Stop! Announce appears.
- File: `duke-great-stop.wav`

**FB Oulet Denied Announce**

- Trigger: immediately when the FB Outlet Denied Announce appears.
- File: `duke-denied.wav`

**No Fast Break Announce**

- Trigger: immediately when the **No Fast Break** secondary announce appears (RR FB hold-up branch, step 2 start in `rim_runner_step_emitter.py`).
- File: `duke-hold-up.wav`
- Wiring: fires from `runStepAnnouncement` in `animationPlayback.js` when the schema-emitted announcement text matches `No Fast Break`. Audio instance stashed on `scene._activeSfx` until `ended` / `error` to prevent mid-clip GC. Same lifecycle pattern as the outlet-pass SFX.




## Shot Make/Miss System

Each shot resolution carries a **variant**: an animation family + the SFX that plays alongside it. The variant is chosen by the backend (deterministic / replayable) from a shot-quality- and shot-type-weighted distribution, then stamped on the result/turn payload for the frontend to execute.

**Field goals:** selected in `resolve_shot()` (see below). **Free throws:** selected in `resolve_free_throw_logic()` (see **Free Throw variant selection**). Both use the same animation families and most of the same SFX files; FT make settle/follow-ups use `free-throw-swish.wav` instead of `swish.wav`.

### Variant Selection — Field Goals (Backend)

Selected inside `resolve_shot()` after `shot_score`, `shot_threshold`, and `shot_type` are finalized (post-defender). The chosen variant is written to `shot_variant` on the result payload so the frontend can dispatch without re-rolling.

**Tier definition** (closeness to outcome threshold, not absolute score):

```
gap = shot_score - shot_threshold
```

- Make tiers (`gap ≥ 0`): `> 150` (great), `> 75` (mid), `else` (squeaker).
- Miss tiers (`gap < 0`): `< -150` (deep miss), `< -75` (mid miss), `else` (near miss).

**Shot type dispatch.** `shot_type` on the result is always one of `"outside"`, `"attack"`, or `"inside"` (set explicitly in `shot_manager.py` — never inferred, never defaulted).

- `"outside"` → Outside distribution.
- `"attack"` or `"inside"` → Attack & Inside distribution.

**Outside — Makes**

- `gap > 150`: 50% Swish, 25% Back of Rim, 10% Little Rattle, 10% Normal Rattle, 5% Heavy Rattle.
- `gap > 75`: 35% Swish, 35% Back of Rim, 10% Little Rattle, 10% Normal Rattle, 10% Heavy Rattle.
- else: 15% Swish, 25% Back of Rim, 19% Little Rattle, 20% Normal Rattle, 20% Heavy Rattle, 1% Bank Off Backboard.

**Outside — Misses**

- `gap < -150`: 49% Clank, 25% Back of Rim, 9% Little Rattle, 9% Normal Rattle, 5% Heavy Rattle, 2% Airball, 1% Bank Off Backboard.
- `gap < -75`: 35% Clank, 35% Back of Rim, 10% Little Rattle, 10% Normal Rattle, 10% Heavy Rattle.
- else: 15% Clank, 15% Back of Rim, 30% Little Rattle, 20% Normal Rattle, 20% Heavy Rattle.

**Attack & Inside — Makes**

- `gap > 150`: 25% Swish, 20% Back of Rim, 30% Bank Off Backboard, 10% Little Rattle, 10% Normal Rattle, 5% Heavy Rattle.
- `gap > 75`: 20% Swish, 20% Back of Rim, 30% Bank Off Backboard, 10% Little Rattle, 10% Normal Rattle, 10% Heavy Rattle.
- else: 10% Swish, 15% Back of Rim, 30% Bank Off Backboard, 15% Little Rattle, 15% Normal Rattle, 15% Heavy Rattle.

**Attack & Inside — Misses**

- `gap < -150`: 35% Clank, 20% Back of Rim, 19% Bank Off Backboard, 5% Little Rattle, 10% Normal Rattle, 10% Heavy Rattle, 1% Airball.
- `gap < -75`: 30% Clank, 20% Back of Rim, 20% Bank Off Backboard, 10% Little Rattle, 10% Normal Rattle, 10% Heavy Rattle.
- else: 15% Clank, 15% Back of Rim, 20% Bank Off Backboard, 30% Little Rattle, 10% Normal Rattle, 10% Heavy Rattle.

### Free Throw variant selection (Backend)

Selected in `resolve_free_throw_logic()` after the **primary** make/miss roll and optional crowd **second-chance** flip. Stamped on the FT turn payload for replay:

- `ft_shot_score` — `(FT × 0.8) + (CH × 0.2)`
- `ft_primary_roll` — `random.randint(1, 100)` on the first roll
- `ft_made_on_second_chance` — `true` when the crowd roll converts a primary miss to a make
- `shot_variant` — animation family (same enum as field goals, e.g. `SWISH`, `LITTLE_RATTLE`, `AIRBALL`)
- Variant extras — same as field goals where applicable (`roll_shot_variant_extras`, shooter `y` for bank)

**Make/miss rule (primary roll):** `makes_shot = ft_primary_roll < ft_shot_score`.

**Delta (tier input):** `delta = ft_shot_score - ft_primary_roll` — always from the **first roll only**, even when a second-chance make changes the final outcome.

**Free Throw Makes**

- **Free Throw Swish** → `free-throw-swish.wav` (clean make; no `swish.wav` on FT)
- **First-roll make** (`ft_primary_roll < ft_shot_score`, not second-chance):
    - if `delta > 30`: 60% Free Throw Swish, 30% Back of Rim, 10% Little Rattle
    - elif `delta > 10`: 30% Free Throw Swish, 30% Back of Rim, 30% Little Rattle, 10% Normal Rattle
    - elif `delta > 0`: 20% Free Throw Swish, 20% Back of Rim, 20% Little Rattle, 20% Normal Rattle, 20% Heavy Rattle
- **Second-chance make** (`ft_made_on_second_chance`):
    - 20% Little Rattle, 35% Normal Rattle, 40% Heavy Rattle, 5% Bank Off Backboard

**Free Throw Misses**

- **Free Throw Miss** → `free-throw-miss.wav` (dedicated miss cue; not `clank.wav`)
- If second-chance converts to a make → **ignore** miss table; use **Free Throw Makes → second-chance make** instead
- **First-roll miss** (`ft_primary_roll >= ft_shot_score`, and not second-chance make):
    - if `delta > -10`: 40% Little Rattle, 30% Free Throw Miss, 20% Clank, 10% Normal Rattle
    - elif `delta > -30`: 30% Normal Rattle, 35% Free Throw Miss, 20% Clank, 10% Heavy Rattle, 5% Little Rattle
    - else: 40% Free Throw Miss, 40% Clank, 15% Normal Rattle, 3% Bank Off Backboard, 2% Airball

**Free Throw SFX bindings**

FT reuses field-goal animation families. **Every make settle / delayed make layer uses `free-throw-swish.wav`, never `swish.wav`.**

| Variant bucket | Make (arrival + follow-up) | Miss |
|---|---|---|
| Free Throw Swish | `free-throw-swish.wav` | — |
| Free Throw Miss | — | `free-throw-miss.wav` |
| Back of Rim | `back-of-rim.wav`, then `free-throw-swish.wav` +150 ms | `back-of-rim.wav` |
| Little / Normal / Heavy Rattle | `rattle-leather.wav` per hop, then `free-throw-swish.wav` on make settle | `rattle-leather.wav` per hop |
| Bank Off Backboard | `bb-rim-swish.wav`, then `free-throw-swish.wav` +100 ms | `bb-clank.wav` / `bb-clank-2.wav` (50/50) |
| Clank | — | `clank.wav` |
| Airball | — | `airball.wav` |

**Free Throw — AIRBALL (miss only)**

Same **grid animation** as field-goal airball: flight ends 2 units short of MSSS, then tween to OOB resting point (`AIRBALL_OOB_HOME` / `AIRBALL_OOB_AWAY`).

- **Final FT miss + AIRBALL:** Same **game outcome** as FG airball — no rebound, possession to defense, next play **BASELINE_INBOUND** (`BIP`). No `calculate_bounce_spot` rebound path.
- **Non-final FT miss + AIRBALL:** Animate to OOB like FG; **do not** proceed to BIP. After OOB, hold for the standard non-final FT miss beat (`bounce_hold`, 1000 ms wall — same as after a normal miss bounce hold), then `ft_return_teleport` (ball back to shooter for the next attempt). No rebound turn.


Unless noted, the ball is visible throughout all sub-steps; existing post-resolution visibility behavior (hide after standard bounce; settle at MSSS on make) is preserved.

- **MADE_SHOT_SWEET_SPOT** (existing make path). Ball flight terminates at `(90, 25)` home / `(10, 25)` away.
- **HOME_RIM_COORDS / AWAY_RIM_COORDS** (existing miss path). Ball flight terminates at `(91, 25)` home / `(9, 25)` away, followed by the standard bounce-spot + rebound resolution.

- **LITTLE / NORMAL / HEAVY RATTLE** (Make or Miss). 50/50 random per shot between two starting positions:

    - **MSSS-start (y-rattle).** Ball flight terminates at MADE_SHOT_SWEET_SPOT. Hops alternate in **y** between `MSSS_y + 1` and `MSSS_y - 1`.
        - Progression Option 1 (50%): `(+1y, -1y)` pair, repeated. Option 2 (50%): `(-1y, +1y)` pair, repeated.
    - **RIM-start (x-rattle).** Ball flight terminates at HOME_RIM_COORDS / AWAY_RIM_COORDS. Hops alternate in **x** between `MSSS_x + 1` and `MSSS_x - 1`. (For home, those are `x=91` and `x=89` — rim is `MSSS_x + 1`. For away, `x=11` and `x=9` — rim is `MSSS_x - 1`. So the rim itself is one of the two hop points.)
        - Progression Option 1 (50%): `(+1x, -1x)` pair, repeated. Option 2 (50%): `(-1x, +1x)` pair, repeated.

    - **Hop count by size:** Little = 1 pair (2 hops). Normal = 2 pairs (4 hops). Heavy = 4 pairs (8 hops).
    - **Hop timing:** 40 ms per hop, linear.
    - **Resolve.** Make → smooth tween to MADE_SHOT_SWEET_SPOT. Miss → smooth tween to the standard bounce spot, then standard rebound resolution.

- **BACKBOARD-MAKE.** Ball flight terminates at the bank point: `x = MSSS_x + 3` home / `MSSS_x - 3` away. Bank `y` is biased by the shooter's grid y so the ball banks toward the side of the backboard near the shooter's lane:

    - `22 < shooter_y < 28` (center): `bank_y = MSSS_y + random.randint(-1, 1)`
    - `shooter_y > 27` (upper side): `bank_y = MSSS_y + random.randint(0, 3)`
    - `shooter_y < 23` (lower side): `bank_y = MSSS_y + random.randint(-3, 0)`

    Boundary semantics: the first branch uses strict `<` / `>`. The elif chain covers everything else exhaustively (e.g. `y=22` → lower; `y=28` → upper; `y=23`, `y=27` → center). Then a ~250 ms tween to MADE_SHOT_SWEET_SPOT.

- **BACKBOARD-MISS.** Three stages: (1) flight to bank point (same `x` and shooter-y-conditional `y` formula as Backboard-Make); (2) ~200 ms tween to rim-graze point at `x = MSSS_x + random.randint(-1, 1)`, `y = MSSS_y + random.randint(-1, 1)`; (3) standard bounce-spot + rebound resolution.

- **AIRBALL** (Miss only). Ball flight terminates **2 grid units short** of MADE_SHOT_SWEET_SPOT — at `(88, 25)` home / `(12, 25)` away. Then the ball continues to the OOB resting point at `(97, 25)` home / `(3, 25)` away. **No rebound attempt.** Possession changes to the defense, and the next step is **BIP** (this deviates from the normal dead-ball turnover progression, which goes to SIP). **Free throws:** same OOB animation; see **Free Throw — AIRBALL** for final vs non-final outcome rules.

### SFX Bindings

`Swish` and `Clank` are the same animation family ("clean rim approach") — the SFX differs purely by outcome. Same for the Backboard family (`BOB+S` on make / `BOB+R` on miss).

When two filenames are listed for a slot (e.g. `bb-clank.wav` / `bb-clank-2.wav`), the file is chosen 50/50 at play time for variety.

| Variant | Make SFX | Make Animation | Miss SFX | Miss Animation |
|---|---|---|---|---|
| Swish / Clank | `swish.wav` | MADE_SHOT_SWEET_SPOT | `clank.wav` | HOME_RIM_COORDS / AWAY_RIM_COORDS |
| Back of Rim (BOR) | `back-of-rim.wav`, then `swish.wav` 150 ms later | MADE_SHOT_SWEET_SPOT | `back-of-rim.wav` | HOME_RIM_COORDS / AWAY_RIM_COORDS |
| Little Rattle | `rattle-leather.wav` × 2 hops, then `swish.wav` follow-up | LITTLE RATTLE → make resolve | `rattle-leather.wav` × 2 hops | LITTLE RATTLE → miss resolve |
| Normal Rattle | `rattle-leather.wav` × 4 hops, then `swish.wav` follow-up | NORMAL RATTLE → make resolve | `rattle-leather.wav` × 4 hops | NORMAL RATTLE → miss resolve |
| Heavy Rattle | `rattle-leather.wav` × 8 hops, then `swish.wav` follow-up | HEAVY RATTLE → make resolve | `rattle-leather.wav` × 8 hops | HEAVY RATTLE → miss resolve |
| Bank Off Backboard | `bb-rim-swish.wav`, then `swish.wav` 100 ms later | BACKBOARD-MAKE | `bb-clank.wav` / `bb-clank-2.wav` (50/50) | BACKBOARD-MISS |
| Airball | — | — | `airball.wav` | AIRBALL → OOB (no rebound, → BIP) |

**SFX timing notes**

- **Rattle SFX**: one `rattle-leather.wav` play fires at the start of each hop (40 ms apart). For make rattles, the net layer plays immediately after the last hop, overlapping the 150 ms settle tween to MSSS — `swish.wav` (field goals) or `free-throw-swish.wav` (free throws).
- **BOR make follow-up**: net layer 150 ms after `back-of-rim.wav` — `swish.wav` (FG) or `free-throw-swish.wav` (FT). Knob: `BOR_MAKE_SWISH_DELAY_MS` in `gameSfx.js`.
- **BANK_MAKE follow-up**: net layer 100 ms after `bb-rim-swish.wav` — `swish.wav` (FG) or `free-throw-swish.wav` (FT). Knob: `BANK_MAKE_SWISH_DELAY_MS` in `gameSfx.js`.
- **All other variants**: SFX fires at ball-flight `onComplete` (the moment the ball lands at its variant-specific flight target).

---

## Sound library strategy (creative brief)

GOB SFX should communicate moment feel without extra on-screen text. Three production pillars:

1. **In-game** — big moments (makes, rebounds, steals, blocks), micro+ (outlet, fouls, trap/press), micro (pass/receive/shot variants), announce stingers, atmosphere.
2. **Non-gameplay** — roster/stats/recruiting/plan screens: calmer, study-time tone vs court intensity.
3. **Functional** — navigation and save/training affordances (mostly built).

**Mandatories:** authentic basketball or premium game tone; each sound has a distinct role; strategic/elegant brand fit. Full creative brief: [`projects/Z-Completed/SFX_Brief.md`](../projects/Z-Completed/SFX_Brief.md).
