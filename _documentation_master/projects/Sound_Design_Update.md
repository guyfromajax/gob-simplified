
SFX Direction

## Backend Terms

- `shot_score_pre_defense`: Existing `resolve_shot()` local variable. This is returned from `calculate_shot_score()` as `pre_defense_shot_score` and represents the shooter/offense value before defensive shot impact is applied.
- `shot_score`: Existing final shot score after defensive impact and later modifiers. This remains the make/miss score compared against `shot_threshold`.
- `shot_defense_score_for_sfx`: New SFX metadata value to expose the defensive shot impact used for missed-shot sound selection. Do not infer this from final `shot_score`.

## Shot Launch SFX

**Outside Shots**

- Trigger: at the moment the ball detaches from the shooter sprite.
- Score source: `shot_score_pre_defense`.
- `< 101`: `three-weak.wav`
- `> 210`: `three-strong.wav`
- Else: `three-medium.wav`

**Attack Shots**

- Trigger: at the moment the ball detaches from the shooter sprite.
- Score source: `shot_score_pre_defense`.
- `< 101`: `inside-shot-weak.wav`
- `> 210`: `inside-shot-strong.wav`
- Else: `inside-shot-medium.wav`

**Inside Shots**

- Trigger: at the moment the ball detaches from the shooter sprite.
- Score source: `shot_score_pre_defense`.
- `< 101`: `inside-shot-weak.wav`
- `> 210`: `inside-shot-strong.wav`
- Else: `inside-shot-medium.wav`

## HCO Pass SFX

**HCO Passes**

- Trigger: at the moment the ball detaches from the passer sprite.
- Scope: HCO skeleton passes only. Do not apply to inbound passes, fast break outlet passes, OREB kickouts, or other non-HCO pass paths unless separately specified.
- Passer `PS > 75`: `pass-strong.wav`
- Passer `PS < 25`: `pass-weak.wav`
- Else: `pass-medium.wav`

**HCO Receptions**

- Trigger: at the moment the ball reaches the receiver sprite.
- Scope: HCO skeleton receptions only. Do not apply to inbound passes, fast break outlet passes, OREB kickouts, or other non-HCO pass paths unless separately specified.
- Receiver `(IQ + CH) > 130`: `receive-strong.wav`
- Receiver `(IQ + CH) < 50`: `receive-weak.wav`
- Else: `receive-medium.wav`

## Shot Result SFX

**Made Shot**

- Trigger: at the moment the ball reaches the basket spot.
- Random choice:
  - `swish.wav`
  - `swish-with-rim.wav`

**Missed Shot**

- Trigger: at the moment the ball reaches the basket spot.
- If `shot_score_pre_defense - shot_defense_score_for_sfx < -150`: `clank-bad.wav`
- Else: `clank.wav`



**Replace All SFX files in the code as follows**
-confirm-1.mp3 -> confirm-1-lowervol.wav
-confirm-2.mp3 -> confirm-2-lowervol.wav
-whistle-1.mp3 -> whistle-1-lowervol.wav
-Timeout - Airhorn.mp3 -> airhorn-lowervol.wav
