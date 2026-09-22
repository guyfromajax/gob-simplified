# Defender-to-ball phase lag — diagnosis

**Measurement only. No engine code changed**, no flags, nothing retuned; `GOB_BOXOUT_CONTEST` stays default `"0"`. Every probe is read-only and reproduces `equiv_v3_reference_70f7dd021_b1a.json` **40/40 on fingerprint and draws** in each cell it ran — stated per table.

## Answer in four lines

1. **Jamie is right that HCO step 1 stands out.** The nearest defender is a mean **14.3–14.8** units from the ball handler there, against **3.7–3.9** once the possession settles. **52–56% of HCO step 1s** have no defender within 10 units, against **0.4–3.4%** of settled steps.
2. **It is not a phase lag.** On HCO, defenders at step N are closest to the ball handler at step **N** at every step index, by a clear margin. The "before or after?" answer for HCO is **neither — they are in phase**.
3. **HCO step 1 is transition, and the geometry is correct.** 99.7% of HCO step 1s are entry steps, and the ball handler is a mean **48.5 units from the rim he is attacking** — he is bringing the ball up. He is genuinely alone. **H4.**
4. **There is a real defect, and it is the one that makes it look wrong: `guard_ball` is essentially never tagged on HCO** — 100% of step 1s and 96–99.8% of all HCO steps have no defender marked as on the ball, including steps where a defender is standing 3 units away.

**There IS a genuine phase lag — but on the other turn types, not HCO.** See §2.

---

## Step 1 — does the symptom exist? Yes.

n=40, seeds 8000–8039, all four cells. Probe RNG-neutral: **fp 40/40, draws 40/40 in every cell.**

### The threshold, picked from the data

Cumulative share of HCO steps with a defender at or inside each distance (sim, `SD=1`):

| ≤ | settled (steps 3, 4+) | step 1 |
|---|---|---|
| 4 | 76.4% | 22.4% |
| 6 | 85.7% | 33.0% |
| 8 | 92.7% | 41.5% |
| **10** | **96.7%** | **46.0%** |
| 15 | 99.6% | 52.8% |
| 25 | 100.0% | 90.1% |

**Threshold = 10 grid units**, chosen as the **p95 of the settled distribution** (HCO steps 3 and 4+, n=36,207). 95% of settled steps have a defender inside it, so beyond it is abnormal *by this engine's own standard* rather than by my guess.

### Nearest defender to the ball handler, by step index

| cell | group | step | steps | **untagged** | near mean | tagged-defender mean | **beyond 10** |
|---|---|---|---|---|---|---|---|
| `SD=1` sim | **HCO** | **1** | 4,778 | **100.0%** | **14.49** | n/a | **54.0%** |
| `SD=1` sim | HCO | 2 | 4,778 | 99.8% | 7.66 | 14.98 | 24.2% |
| `SD=1` sim | HCO | 3 | 4,739 | 98.0% | **3.79** | 12.75 | 2.2% |
| `SD=1` sim | HCO | 4+ | 31,468 | 96.9% | **3.93** | 8.61 | 3.4% |
| `SD=1` played | **HCO** | **1** | 4,721 | **100.0%** | **14.78** | n/a | **55.6%** |
| `SD=1` played | HCO | 4+ | 30,945 | 96.4% | 3.88 | 9.38 | 3.1% |
| `SD=0` sim | **HCO** | **1** | 4,967 | **100.0%** | **14.28** | n/a | **51.8%** |
| `SD=0` sim | HCO | 4+ | 32,519 | 96.1% | 3.72 | 8.87 | 1.2% |
| `SD=0` played | **HCO** | **1** | 4,944 | **100.0%** | **14.59** | n/a | **53.5%** |
| `SD=0` played | HCO | 4+ | 32,278 | 95.8% | 3.73 | 9.31 | 1.2% |

| cell | group | step | steps | untagged | near mean | tagged mean | beyond 10 |
|---|---|---|---|---|---|---|---|
| `SD=1` sim | other | 1 | 9,299 | 85.7% | 9.23 | 0.56 | 33.7% |
| `SD=1` sim | **other** | **2** | 7,105 | 67.8% | **15.72** | 3.35 | **59.3%** |
| `SD=1` sim | **other** | **3** | 6,486 | 78.7% | **14.92** | 2.09 | **66.8%** |
| `SD=1` sim | other | 4+ | 9,013 | 53.3% | 7.41 | 2.33 | 23.9% |

(The other three cells match to within ~1 pp on every row; the full table is identical in shape.)

**Three things fall out of this.**

- **HCO step 1 is ~4× worse than settled play on distance and ~20× worse on the beyond-10 share.** The impression is correct and it is not marginal.
- **Where a defender IS tagged on HCO, he is the wrong one.** The tagged defender averages 8.6–15.0 units away while the nearest is 3.7–8.2. On the other turn types the tagged defender is the close one (0.42–3.35). So HCO's on-ball tag, on the rare occasions it exists, is not tracking the nearest man.
- **The other turn types are worse than HCO at steps 2–3** (59–67% beyond 10). That is a separate problem and §2 shows it is a genuine phase error.

## Step 2 — is it a phase lag? For HCO, no. For the rest, yes.

Mean distance from the **defenders at step N** to the **ball handler at N−1 / N / N+1** (nearest defender each time). Probe RNG-neutral 40/40 in all four cells.

| cell | group | step | n | → bh(N−1) | **→ bh(N)** | → bh(N+1) | verdict |
|---|---|---|---|---|---|---|---|
| `SD=1` sim | HCO | 2 | 4,739 | 18.70 | **7.68** | 8.16 | **in phase** |
| `SD=1` sim | HCO | 3 | 4,738 | 18.28 | **3.79** | 5.62 | **in phase** |
| `SD=1` sim | HCO | 4+ | 26,646 | 5.38 | **3.72** | 4.76 | **in phase** |
| `SD=1` sim | **other** | **2** | 6,486 | **14.08** | 16.89 | 15.91 | **N−1 — LAGGING** |
| `SD=1` sim | **other** | **3** | 4,316 | 17.24 | 15.97 | **12.32** | **N+1 — LEADING** |
| `SD=1` sim | other | 4+ | 4,697 | 5.77 | **3.28** | 5.17 | in phase |
| `SD=1` played | HCO | 2 | 4,682 | 18.27 | 8.22 | **7.40** | N+1 (8.22 vs 7.40 — marginal) |
| `SD=1` played | HCO | 3 | 4,681 | 18.09 | **3.75** | 5.56 | in phase |
| `SD=1` played | HCO | 4+ | 26,174 | 5.35 | **3.66** | 4.70 | in phase |
| `SD=1` played | **other** | **2** | 6,522 | **14.64** | 17.38 | 16.26 | **N−1 — LAGGING** |
| `SD=1` played | **other** | **3** | 4,330 | 17.91 | 16.47 | **12.94** | **N+1 — LEADING** |

`SD=0` reproduces this exactly in both arms.

**A correction I have to make against my own first pass.** I initially counted *which of the three was smallest* per step (an argmin), and that said HCO step 4+ was lagging — N−1 won 49–51% of steps against N's 37–38%. **That reading was wrong.** By magnitude the same bucket is 5.38 / **3.72** / 4.76 — clearly minimised at N. The argmin misleads because when the ball handler barely moves between steps all three distances are nearly equal and noise picks the winner. **Magnitude is the right test and it says HCO is in phase.** I would have reported a lag that is not there.

**The other turn types are a different story and the effect is unambiguous:** at step 2, defenders are **14.08** from where the ball handler *was* and **16.89** from where he *is* — they are a step behind. At step 3 it inverts to leading (12.32 at N+1 against 15.97 at N). That is a real timing error, it is consistent across both arms and both footings, and it is **not** what Jamie was looking at — it is on inbounds, DREB, fast breaks and the trap/press families.

## Step 3 — the hypotheses

### H1 — HCO step 1 places defenders from a stale or default position — **contradicted as stated**

Defenders on step 1 are not at stale coordinates. They are at their own end of the floor because the possession has just changed and they are retreating. The trace (§5) shows this directly, and the aggregate confirms it: n=4,801 HCO step 1s, sim, `SD=1`, probe 40/40 —

| what HCO step 1 is | share |
|---|---|
| `hco_entry_handoff_hold` | 48.5% |
| `hco_entry_handoff_converge` | 35.0% |
| `hco_entry_kickout_positioning` | 8.4% |
| `hco_entry_walkup_fallback` | 3.2% |
| `final_turn_entry_walkup` | 2.1% |
| `hco_entry_walkup` | 1.3% |
| everything else | 1.5% |

**99.7% of HCO step 1s are entry/transition steps**, and the ball handler at step-1 end is a mean **48.5 units from the rim he is attacking**, with **41.4%** still on his own half. He is bringing the ball up.

A *related but different* mechanism is real: the entry builders place defenders toward their setup coords **without reference to the ball handler**, so nobody is assigned to him during the entry. That is the tagging defect below, not a stale-coordinate defect.

### H2 — `_bh_defender_pos` resolves the wrong step index — **contradicted**

Measured over 20 games (probe 20/20): `_bh_defender_pos` is called 4,269 times and returns `None` **55.0%** of the time — **2,346 of 2,346 because `roles["defender"]` is `None`**, and **zero** because the defender was not in `def_lineup`. There is no step-index error; the function simply is not given a defender. (The `def_lineup` count being zero also confirms the position-lookup fix from `reports/position-lookup-2-2026-09-19.md` is holding.)

When it *does* resolve, the emitter behaves: `_build_step_destinations_and_actions` ran 28,905 times, 13,504 of them with a `bh_defender_pos`, and wrote **13,504 `guard_ball` tags** — exactly one per call. The tag logic is correct.

### H3 — defender and ball-handler coords describe different instants — **contradicted for HCO, supported for the rest**

Per §2. HCO is in phase at every step index in both arms and both footings. The non-HCO families are genuinely off by a step at step 2 (lagging) and step 3 (leading).

### H4 — the defenders are right and the ball handler is genuinely alone — **supported, for HCO steps 1–2**

The geometry at HCO step 1 is transition geometry: the offense has the ball near half-court or in its own backcourt, and the defense is still at the other end. That is what the trace shows and what the reason distribution says. **The animation is correct; the impression that "the defense is nowhere" is correct too — that is what transition looks like.**

### Not in the hypothesis list, and the one I would act on: the `guard_ball` tag is missing

- **100.0%** of HCO step 1s and **96–99.8%** of *all* HCO steps carry no `guard_ball` tag, including steps where a defender is 3 units away.
- `transition_bridge.build_walk_up_step:350` assigns `actions[pid] = "cut" if _is_offense_player(...) else "guard_offball"` — **every defender on an entry step is `guard_offball` unconditionally.** There is no on-ball concept in that builder.
- The action map lives **only on `start`**: across 2,477 emitted steps, `start.action` is populated on 2,477 and `end.action` on **0**.

If the renderer draws `guard_ball` differently from `guard_offball` — a pressure stance, a closer sprite, anything — then **no HCO defender is ever drawn as being on the ball**, even when the geometry has him right there. That is a very plausible source of "the ball handler does not have a defender anywhere near it" as a visual impression on steps where the distance is in fact 3–4 units.

**What I did not establish:** the emitter writes 13,504 `guard_ball` tags per 20 games but only ~291 per game survive into the emitted payload. Roughly half the builder calls are the throwaway pre-pass inside `_uess_sync_emitted_shot_coords`, which accounts for some of it; I did not trace the remainder. So *why* HCO specifically ends up at 3% tagged while the other families reach 32–53% is **named but not fully accounted for**.

## Step 4 — sim vs played

**No parity finding. The two arms are the same.**

| metric (`SD=1`) | sim | played |
|---|---|---|
| HCO step 1, near mean | 14.49 | 14.78 |
| HCO step 1, beyond 10 | 54.0% | 55.6% |
| HCO step 1, untagged | 100.0% | 100.0% |
| HCO step 4+, near mean | 3.93 | 3.88 |
| other step 2, → bh(N−1) / bh(N) | 14.08 / 16.89 | 14.64 / 17.38 |

Every row matches within ~1.6%, and `SD=0` behaves the same. Whatever this is, it is not an arm-parity problem — consistent with B1-A having put both arms on the same emitter.

## Step 5 — trace: 6 HCO turns, first three steps (sim, `SD=1`, seed 8000)

```
--- turn 1 (18 steps) ---
 step 1  BH c13c8088 at [42.0, 28.0]  handle_ball  reason=hco_entry_handoff_hold
     PF 80f3ca79 [68.7, 24.1] guard_offball d=26.95      SF f608a824 [63.5, 25.1] guard_offball d=21.73
     SG a0a0f2d7 [65.7, 25.4] guard_offball d=23.81      PG 104c7b0f [67.0, 25.0] guard_offball d=25.18
     C  7219a92c [65.1, 26.1] guard_offball d=23.18
 step 2  BH c13c8088 at [64.0, 25.0]  handle_ball  reason=hco_entry_walkup
     PF [84.0,29.0] d=20.40   SF [70.0,17.0] d=10.00   SG [71.0,34.0] d=11.40
     PG [67.0,25.0] d=3.00    C  [84.0,22.0] d=20.22        — all guard_offball
 step 3  BH c13c8088 at [64.0, 25.0]  handle_ball  reason=None
     identical to step 2 — PG 3.00 away, still guard_offball

--- turn 3 (16 steps) — the clearest one ---
 step 1  BH e590d342 at [18.0, 24.0]  handle_ball  reason=hco_entry_handoff_converge
     PF [45.4,10.5] d=30.53   SF [42.1,29.3] d=24.63   SG [57.9,24.7] d=39.90
     PG [58.2,28.4] d=40.49   C  [38.8,36.4] d=24.22       — all guard_offball
 step 2  BH c13c8088 at [12.3, 32.0]  receive  reason=hco_entry_handoff_pass
     PF d=44.24  SF d=37.13  SG d=53.19  PG d=52.67  C d=33.28   — all guard_offball
 step 3  BH c13c8088 at [68.0, 36.0]  handle_ball  reason=hco_entry_walkup
     PF [80.0,19.0] d=20.81   SF [80.0,37.0] d=12.04   SG [73.0,18.0] d=18.68
     PG [71.0,34.0] d=3.61    C  [84.0,30.0] d=17.09       — all guard_offball

--- turn 5 (14 steps) ---
 step 1  BH 104c7b0f at [49.0, 42.0]  handle_ball  reason=hco_entry_handoff_hold
     PF [12.0,21.0] d=42.54   PG [32.0,25.0] d=24.04   SF [26.0,16.0] d=34.71
     C  [12.0,29.0] d=39.22   SG [26.0,34.0] d=24.35       — all guard_offball
 step 2  BH 104c7b0f at [36.0, 25.0]  handle_ball  reason=hco_entry_walkup
     PG [32.0,25.0] d=4.00, the rest 13.45-24.33            — all guard_offball
```

(Turns 2, 4 and 6 are the same shape: an `hco_entry_*` step 1, a handoff or kickout pass at step 2, then the ball handler arriving at his setup spot with the PG-slot defender 3–4 units away — and still tagged `guard_offball`.)

**Read it this way.** Turn 3 step 2 is the extreme case: the ball handler is at x = 12.3 and the five defenders are at x = 45–65, 33 to 53 units away. Nothing is broken — the offense has just taken possession at its own end and the defense is at the other. By step 3 the ball handler has crossed to x = 68 and the PG-slot defender is 3.61 units from him. **That defender is guarding the ball, and the payload says `guard_offball`.**

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039 per cell, `SEED_DEFENSES=1` and `=0`, both arms. **sim arm** = `_is_full_simulation` True throughout; **played arm** = False only inside the four gated Animator methods at Pattern A. The H2 gate counts and the face/action check are 20 games and 1 game respectively, sim `SD=1`, and are labelled as such. All probes hook `sync_lineup_coords_from_turn`, so they read the **final** `animation_steps` for **every** turn type — the payload the frontend renders — not one emitter's intermediate output. Defenders are identified as the lineup of the team that is not `turn_result["offense_team_id"]`, so a possession flip before the end-of-turn sync cannot mislabel them.

## The fix, described in one paragraph, not built

**The tag, not the geometry, is what I would change.** The entry builders in `transition_bridge` have no notion of an on-ball defender and tag all five `guard_offball`; the skeleton steps have the notion but only receive a defender 45% of the time because `roles["defender"]` is `None` on 55% of `_bh_defender_pos` calls. The smallest honest change is to give the entry builders the same on-ball resolution the skeleton steps already use — pass the defense lineup and the ball-handler id in, resolve the nearest defender (or the matchup defender) and tag him `guard_ball` — and separately to find out why `roles["defender"]` is unset on HCO more than half the time. **Cost:** the action map is render-only — `_archetype_for_action` maps `guard_ball` and `guard_offball` to the same `cruise` archetype, so step timing does not change and no RNG is consumed, which means it should be **reference-neutral**; that has to be verified rather than assumed, because a re-cut would be needed if anything downstream reads the action. **It would not close the distance gap at HCO step 1, and should not** — that gap is transition and it is correct.

**The non-HCO phase error at steps 2–3 is a separate defect** with a separate cause, and this pass did not look for it.

## Not covered

- **No engine code changed. No fix built.** No flags, nothing retuned; `GOB_BOXOUT_CONTEST` stays default `"0"`.
- **Not established:** why only ~3% of HCO steps carry a surviving `guard_ball` tag when the emitter writes one on 46.7% of its builds; and why `roles["defender"]` is `None` on 55% of HCO calls.
- **Not investigated:** the non-HCO lag/lead at steps 2–3 — which family causes it, and whether it is one emitter or several.
- **Not checked:** what the frontend actually does with `guard_ball` vs `guard_offball`. The claim that the missing tag is visible on screen is an inference from the payload, not an observation of the renderer.
