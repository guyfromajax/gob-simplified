
SFX Direction

## Backend Terms

- `shot_score_pre_defense`: Existing `resolve_shot()` local variable. This is returned from `calculate_shot_score()` as `pre_defense_shot_score` and represents the shooter/offense value before defensive shot impact is applied.
- `shot_score`: Existing final shot score after defensive impact and later modifiers. This remains the make/miss score compared against `shot_threshold`.
- `shot_defense_score_for_sfx`: Existing SFX metadata value that exposes defensive shot impact. Current missed-shot SFX no longer branches on this value, but keep the field available for future sound-selection rules.

## Shot Launch SFX

<!-- **Outside Shots**

- Trigger: at the moment the ball detaches from the shooter sprite.
- Score source: `shot_score_pre_defense`.
- `< 101`: `three-weak.wav`
- `> 210`: `three-strong.wav`
- Else: `three-medium.wav`

**Attack Shots**

- Trigger: at the moment the ball detaches from the shooter sprite.
- Score source: `shot_score_pre_defense`.
- `< 101`: `inside-shot-weak.wav`
- `> 210`: `attack-shot-strong.wav`
- Else: `attack-shot-medium.wav`

**Inside Shots**

- Trigger: at the moment the ball detaches from the shooter sprite.
- Score source: `shot_score_pre_defense`.
- `< 101`: `inside-shot-weak.wav`
- `> 210`: `inside-shot-strong.wav`
- Else: `inside-shot-medium.wav` -->

**All Shot Types (Inside, Attack, Outside)**
- Trigger: at the moment the ball detaches from the shooter sprite.
- Score source: `shot_score_pre_defense`.
- `< 101`: `three-weak.wav`
- `> 210`: `three-strong.wav`
- Else: `attack-shot-medium.wav`


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

## Shot Result SFX

**Made Shot (HCO, OREB Putback, Fast Break, HCT, FCP)**

- Trigger: at the moment the ball reaches the basket spot.
- `swish.wav`

**Missed Shot (HCO, OREB Putback, Fast Break, HCT, FCP)**

- Trigger: at the moment the ball reaches the basket spot.
- `clank.wav`

**Free Throw**

- Trigger: at the moment the ball reaches the basket spot.
- Made: `free-throw-swish.wav`
- Missed: `free-throw-miss.wav`

**Replace All SFX files in the code as follows**
-confirm-1.mp3 -> confirm-1-lowervol.wav
-confirm-2.mp3 -> confirm-2-lowervol.wav
-whistle-1.mp3 -> whistle-1-lowervol.wav
-Timeout - Airhorn.mp3 -> airhorn-lowervol.wav


## Court Event SFX

Court event stingers are **in scope** for the secondary announcement ribbon and the Defense Matchups modal. They are **not** primary-tier whistles (`playAnnouncementSfx`); route them through the court gameplay SFX manager (`gameSfx.js` — preload pools, `playGameSfx`, optional `?debug_sfx=1`).

**Shared rules**

- Volume: **0.7** (same as other court SFX).
- **One SFX per show** — fire once when the UI moment appears; do not stack on re-entrant or idempotent announce calls for the same visible show.
- Assets live under `FrontEnd/static/sounds/`; use root-relative `/sounds/` + `encodeURIComponent(filename)`.

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
- File: `inside-shot-weak.wav`



## Shot Make/Miss System

Each shot resolution carries a **variant**: an animation family + the SFX that plays alongside it. The variant is chosen by the backend (deterministic / replayable) from a shot-quality- and shot-type-weighted distribution, then stamped on the result/turn payload for the frontend to execute.

Free throws are out of scope — their existing animation and SFX are unchanged.

### Variant Selection (Backend)

Selected inside `resolve_shot()` after `shot_score`, `shot_threshold`, and `shot_type` are finalized (post-defender). The chosen variant is written to a new field on the result payload (e.g. `shot_variant`) so the frontend can dispatch without re-rolling.

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

### Ball Resolve Animations

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

- **AIRBALL** (Miss only). Ball flight terminates **2 grid units short** of MADE_SHOT_SWEET_SPOT — at `(88, 25)` home / `(12, 25)` away. Then the ball continues to the OOB resting point at `(97, 25)` home / `(3, 25)` away. **No rebound attempt.** Possession changes to the defense, and the next step is **BIP** (this deviates from the normal dead-ball turnover progression, which goes to SIP).

### SFX Bindings

`Swish` and `Clank` are the same animation family ("clean rim approach") — the SFX differs purely by outcome. Same for the Backboard family (`BOB+S` on make / `BOB+R` on miss).

When two filenames are listed for a slot (e.g. `swish.wav` / `swish-2.wav`), the file is chosen 50/50 at play time for variety.

| Variant | Make SFX | Make Animation | Miss SFX | Miss Animation |
|---|---|---|---|---|
| Swish / Clank | `swish.wav` / `swish-2.wav` (50/50) | MADE_SHOT_SWEET_SPOT | `clank.wav` | HOME_RIM_COORDS / AWAY_RIM_COORDS |
| Back of Rim (BOR) | `back-of-rim.wav`, then `swish.wav` / `swish-2.wav` 150 ms later | MADE_SHOT_SWEET_SPOT | `back-of-rim.wav` | HOME_RIM_COORDS / AWAY_RIM_COORDS |
| Little Rattle | `rattle-leather.wav` × 2 hops, then `swish.wav` / `swish-2.wav` follow-up | LITTLE RATTLE → make resolve | `rattle-leather.wav` × 2 hops | LITTLE RATTLE → miss resolve |
| Normal Rattle | `rattle-leather.wav` × 4 hops, then `swish.wav` / `swish-2.wav` follow-up | NORMAL RATTLE → make resolve | `rattle-leather.wav` × 4 hops | NORMAL RATTLE → miss resolve |
| Heavy Rattle | `rattle-leather.wav` × 8 hops, then `swish.wav` / `swish-2.wav` follow-up | HEAVY RATTLE → make resolve | `rattle-leather.wav` × 8 hops | HEAVY RATTLE → miss resolve |
| Bank Off Backboard | `bb-rim-swish.wav` / `bb-swish.wav` (50/50) | BACKBOARD-MAKE | `bb-clank.wav` / `bb-clank-2.wav` (50/50) | BACKBOARD-MISS |
| Airball | — | — | `airball.wav` | AIRBALL → OOB (no rebound, → BIP) |

**SFX timing notes**

- **Rattle SFX**: one `rattle-leather.wav` play fires at the start of each hop (40 ms apart). For make rattles, a `swish.wav` / `swish-2.wav` plays immediately after the last hop, overlapping the 150 ms settle tween to MSSS.
- **BOR make follow-up**: `swish.wav` / `swish-2.wav` plays 150 ms after `back-of-rim.wav` — long enough to read as "rim → through the net," short enough to feel like one event. Knob: `BOR_MAKE_SWISH_DELAY_MS` in `gameSfx.js`.
- **All other variants**: SFX fires at ball-flight `onComplete` (the moment the ball lands at its variant-specific flight target).
