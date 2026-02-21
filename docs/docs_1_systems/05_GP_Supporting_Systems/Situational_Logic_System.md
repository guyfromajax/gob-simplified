# Situational Logic (Q4/OT)

**Score Delta** = Offense Team Score − Defense Team Score (zero in the case of a tie).

All logic below applies only when **quarter ≥ 4**. Evaluate the time-band table first to determine Slow It Down, Quick Shot, shot ratios, and Force Foul; then apply Execution.

---

## Time-band table (source of truth)

**Time Remaining 2:01 – 3:00**
- If Score Delta ≥ 12 → Slow It Down = True
- Else if Score Delta < -12 and > -24 → Quick Shot = True  
  - Outside Shot Chance = 60%, Attack = 20%, Inside = 20%
- Force Foul = False

**Time Remaining 1:01 – 2:00**
- If Score Delta ≥ 9 → Slow It Down = True
- Else if Score Delta < -9 and > -18 → Quick Shot = True  
  - Outside = 70%, Attack = 20%, Inside = 10%
- Force Foul = False

**Time Remaining 0:31 – 1:00**
- If Score Delta ≥ 3 → Slow It Down = True
- Else if Score Delta < -3 and > -12 → Quick Shot = True  
  - Outside = 80%, Attack = 15%, Inside = 5%
- Force Foul: True if 3 < Score Delta < 12, else False

**Time Remaining 0:01 – 0:30**
- If Score Delta ≥ 1 → Slow It Down = True
- Else if Score Delta < -1 and > -9 → Quick Shot = True  
  - If Score Delta < -2: Outside Shot Chance = 100%  
  - Else: run normal playcall logic
- Force Foul: True if 1 < Score Delta < 9, else False

When Score Delta falls in neither Slow It Down nor Quick Shot for that band → use normal logic (no tempo or shot overrides).

---

## Execution

**When Slow It Down applies (per time-band table):**
- Calculate Force Foul at the BIP or SIP step if applicable; otherwise at the very beginning of the HCO step.
- If Force Foul = True: defense commits a foul immediately on the pass receiver of the BIP/SIP pass (pass must be animated first), or at HCO on the last rebounder; `time_elapsed = random.randint(1, 3)`; process next step accordingly (goal: get to bonus and force free throws).
  - The player being fouled is the offense player receiving the inbound pass on BIP & SIP steps, or the offense player who holds the ball entering the HCO step (no passes); the fouling defender is the defender closest to the player being fouled at the moment of the foul.
  - Foul animation: move the defensive fouling player's sprite to the offensive player being fouled sprite, execute the announcement system with the fouling player image and text "Quick Foul".
- If Force Foul = False: proceed to next step.
- Override Offense Team’s Fast Break setting to 0 (temp override; revert when Slow It Down no longer applies).
- Next step (if Force Foul = False): offense tempo = "slow".

**When Quick Shot applies (per time-band table):**
- Offense tempo = "fast".
- Play focus / shot chances = per time-band table (Outside / Attack / Inside ratios, or 100% outside / normal logic in 0:01–0:30 as specified).
- Override Defense Team's FCP & HCT settings to 0 (temp override; revert when Quick Shot no longer applies).

Temp overrides (Fast Break, FCP, HCT) are re-evaluated each turn and revert when the situation no longer applies.

---

## Summary

**Force Foul after inbound:** When Slow It Down + Force Foul apply, we set a pending Force Foul after each BIP or SIP. On the next turn we **run the Force Foul first** (before any state routing). That way the foul is executed whether the next step would have been HCO, HCT, or FCP—and we avoid running next-turn choice logic (e.g. HCO vs HCT vs FCP) when it would only be overwritten by the foul result.

**Force Foul after DREB:** On a defensive rebound (HCO shot miss → DREB), we **evaluate Force Foul immediately**. If Slow It Down + Force Foul apply, we execute the foul right away: we do not run the normal “next step” logic (no Fast Break vs HCO decision, no outlet pass). The victim is the last rebounder; the fouling defender is the defender closest to that rebounder. We inject a FOUL turn and then enter the standard defensive non-shooting foul flow (possession flip, SIDE_INBOUND or FREE_THROW). Animation: no outlet pass; on the FOUL turn we animate the defender moving to the rebounder and announce “Quick Foul.”
