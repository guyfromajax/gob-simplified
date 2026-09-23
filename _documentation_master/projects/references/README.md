# equiv-v3 references

Each file is a frozen baseline of the equiv-v3 worker at one tree: per-seed rows for
seeds 8000–8039, both arms, and (from `..._merged` onward) both footings in one file.

**Use the newest non-superseded reference.** A superseded file is kept, never deleted —
it is what the matching kill switch reproduces, which is how a rollback is verified.

## Footing (every reference)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM. **sim arm** =
`_is_full_simulation` True throughout; **played arm** = False only inside the four gated
Animator methods at Pattern A.

## Current

| file | tree | what it baselines |
|---|---|---|
| **`equiv_v3_reference_09f1b0ca9_boxout.json`** | `09f1b0ca9` (2026-09-23) | **CURRENT, both arms, both footings.** Box-out contest ON by default, **two-directional**: when a defensive crasher has an offensive crasher within `BOXOUT_PAIR_RADIUS` 8.0 the two contest the box-out — `(0.4·RB + 0.4·ST + 0.1·IQ + 0.1·CH) × rand(1,6)`, a tie to the defender — and the **loser's** crash destination is pushed back off the rim by `BOXOUT_PUSHBACK_FRACTION` 0.5 of his remaining travel. Either side can lose: the defender won **48.3%** of 8,792 contests. Nothing retuned. **Team-level rebounding does not move** — at n=120 seed-paired, OREB −0.36 ±1.27, DREB −0.53 ±1.49, OREB share −0.42 ±1.59, and no metric clears its CI — while per-player P(rebound \| winner) is **1.69×** P(rebound \| loser). **Both footings move and every seed differs in all four cells**: the box-out is scheme-independent, keying on crasher geometry rather than man vs zone, so SD=0 pairs at a similar rate to SD=1 (40.2% vs 35.8% of defenders). See `reports/boxout-flip-2026-09-23.md`. |

## Posture-footing baselines

Not part of the supersession chain above. A change that only fires at a non-default **posture**
is invisible to the ordinary reference, because that reference runs the unset posture (base
man). These files run `EQUIV_MAN_POSTURE=<posture>` instead and are the thing such a change is
measured against.

| file | tree | footing | what it baselines |
|---|---|---|---|
| `equiv_v3_loose_baseline_ef00985ce.json` | `ef00985ce` (2026-09-23) | `EQUIV_MAN_POSTURE=loose`, `SEED_DEFENSES=1`, both arms, n=40 | Both new flags OFF. Cut because `GOB_MAN_LOOSE_SAG_AXIS` is invisible to `equiv_v3_reference_09f1b0ca9_boxout.json` — `HELP_BASKET_PULL["normal"]` is 0.0, so base man is byte-identical either way. Double re-baselined (80/80 twice); `GOB_MAN_LOOSE_SAG_AXIS=1` moves **every** seed (0/80). See `reports/loose-sag-and-cutoff-gate-2026-09-23.md`. |

## Superseded — kept deliberately

| file | tree | superseded by | reproduced today by |
|---|---|---|---|
| `equiv_v3_reference_f2a060488_manhelpshade.json` | `f2a060488` | `09f1b0ca9` | **`GOB_BOXOUT_CONTEST=0`** — verified 40/40 on fingerprint AND draws in all four cells at `09f1b0ca9`, before the re-cut, with every box-out counter at zero. It baselines the **man** weak-side help shade: a man off-ball help defender sags toward the rim he is defending, scaled by how weak-side he is. |
| `equiv_v3_reference_32db56c77_helpshade.json` | `32db56c77` | `f2a060488` | **`GOB_MAN_HELP_SHADE=0`** — verified 40/40 on fingerprint AND draws in all four cells at `f2a060488`, before the re-cut, with every man-shade counter at zero. It baselines the **zone** weak-side help shade: a zone defender with a man in his area sags toward the rim, scaled by how weak-side he is. |
| `equiv_v3_reference_5ea94694f_sinkescape.json` | `5ea94694f` | `32db56c77` | **`GOB_ZONE_HELP_SHADE=0`** — verified 40/40 on fingerprint AND draws in all four cells at `32db56c77`, before the re-cut. It baselines the zone sink escape: an empty-area zone defender may leave his polygon to the extent the movement is rim-ward, guardrails `RIM_FLOOR` 4.0 and `MIN_SEPARATION` 2.0. |
| `equiv_v3_reference_5cc98ee3e_freeze.json` | `5cc98ee3e` | `5ea94694f` | **`GOB_ZONE_SINK_ESCAPE=0`** — verified 40/40 on fingerprint AND draws in all four cells at `5ea94694f`, before the re-cut, with every escape counter at zero. |
| `equiv_v3_reference_70f7dd021_b1a.json` | `70f7dd021` | `5cc98ee3e` | **`GOB_PLACEMENT_FREEZE=0 GOB_PLACEMENT_SINGLE_BUILD=0`** — verified 40/40 on fingerprint AND draws in all four cells at `5cc98ee3e`, before the re-cut. `GOB_PLACEMENT_FREEZE=0` alone is sufficient: Stage 3 is inert unless the freeze is on. |
| `equiv_v3_reference_ec4f5acfc_poslookup2.json` | `ec4f5acfc` | `70f7dd021` | **`GOB_SIM_BUILD_ANIM_FOR_EMITTER=0`** — verified 40/40 on all four cells at `70f7dd021`. `GOB_SIM_HCO_COORD_WRITE` and `GOB_SIM_CRASH_APPLY` are kept as this switch's partners: they are what write the sim arm's HCO coords when B1-A is off. |
| `equiv_v3_reference_456e2cdd9_reboundarrival.json` | `456e2cdd9` | `ec4f5acfc` | `GOB_LINEUP_POSITION_LOOKUP=0` — verified 40/40 on all four cells at `ec4f5acfc` |
| `equiv_v3_reference_bf7ed1181_crashmodela.json` | `bf7ed1181` | `456e2cdd9` | `GOB_REBOUND_FROM_ARRIVAL=0` — verified 40/40 on all four cells at that flip |
| `equiv_v3_reference_d91679bef_foulweight.json` | `d91679bef` | `bf7ed1181` | `GOB_CRASH_SHOT_AWARE=0` — verified 40/40 at that flip |
| `equiv_v3_reference_c1958f8f6_rings.json` | `c1958f8f6` | `d91679bef` | `GOB_FOUL_ON_BALL_WEIGHT=0` — verified 40/40 at that flip |
| `equiv_v3_reference_1fd08c080_zonesink.json` | `1fd08c080` | `c1958f8f6` | `GOB_ZONE_SINK=0` reproduces the pre-sink rings tree 40/40 |
| `equiv_v3_reference_29e6a6792_merged.json` | `29e6a6792` | `c1958f8f6` | the develop merge before the zone rings were repaired; kept so develop's own contribution stays separable |
| `equiv_v3_sim_reference_9910cd6fd.json` | `9910cd6fd` | `c1958f8f6` | **sim arm only.** The played reference of that era was the commit `d9a4f1517`, not a file. |
| `equiv_v3_sim_reference_4f856721a.json` | `4f856721a` | `9910cd6fd` | **no longer reachable.** `GOB_SIM_CRASH_APPLY=0 GOB_SIM_CRASH_CLOCK=0` still disables the crash work, but zone placement changed underneath it, so the flags-off path is a switch, not a time machine. |

## When you cut a new one

1. Verify the kill switch first: the previous reference must still reproduce **40/40 on
   all four cells** with the new flag off. If it does not, the change is not
   flag-isolated and the flip should stop.
2. Cut the reference, then **run the worker a second time and confirm the new reference
   reproduces 40/40 byte-identical** — a double re-baseline. A reference that cannot
   reproduce itself is not a reference.
3. Add the row above, move the old file to *Superseded*, and record which flag setting
   reproduces it. **Do not delete the old file.**
