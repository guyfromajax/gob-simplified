
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
