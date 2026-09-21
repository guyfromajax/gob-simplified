# Non-HCO defender phase error — localised

**Measurement only. No engine code changed**, no flags, nothing retuned; `GOB_BOXOUT_CONTEST` stays default `"0"`. Every probe is read-only and reproduces `equiv_v3_reference_70f7dd021_b1a.json` **40/40 on fingerprint and draws** in each cell it ran — stated per table.

## Answer

**It is the trap. There is no timing error, and I am withdrawing the claim I made in `reports/defender-phase-2026-09-20.md` §2.**

The non-HCO "phase error" was an artefact of pooling **inbounds** with everything else. Inbounds carry **68.6%** of all beyond-10 steps, and on them the ball handler is **literally out of bounds** — 100.0% of `SIDE_INBOUND` steps 1–2 and 100.0% of `BASELINE_INBOUND` step 2 — and **stationary for a step** (100.0% / 95.0% frozen). When the ball handler does not move, the distance to `bh(N−1)` and the distance to `bh(N)` are **the same number by construction**, so the "which is smaller" comparison is degenerate. You cannot guard a man who is standing behind the baseline, and the engine correctly does not try.

The only other family with meaningful mass is the **fast break**, and there the defenders are **chasing and closing**, not lagging: on `rim_runner` step 3 the ball handler covers **40.3** units and the apparent gap is only **5.75** — the defence followed **86%** of it.

**Nothing survives to Step 3.** No code path to name.

---

## Step 1 — splitting "other" into its actual families

n=40, seeds 8000–8039, all four cells. Probe RNG-neutral: **fp 40/40, draws 40/40 in every cell.**

### Which family carries the mass (sim, `SD=1`, all step indices)

| family | steps | beyond 10 | share of its own steps | **% of all beyond-10** |
|---|---|---|---|---|
| **BASELINE_INBOUND** | 9,544 | 7,885 | **82.6%** | **42.1%** |
| **SIDE_INBOUND** | 4,980 | 4,956 | **99.5%** | **26.5%** |
| HCO | 45,763 | 4,911 | 10.7% | 26.2% |
| FAST_BREAK/covert_release | 598 | 337 | 56.4% | 1.8% |
| FCP | 6,968 | 316 | 4.5% | 1.7% |
| FAST_BREAK/rim_runner | 827 | 207 | 25.0% | 1.1% |
| HCT | 5,794 | 73 | 1.3% | 0.4% |
| OREB | 1,149 | 46 | 4.0% | 0.2% |
| FAST_BREAK/after_steal | 276 | 4 | 1.4% | 0.0% |
| **DREB** | 1,767 | **0** | **0.0%** | 0.0% |

**Two families are the whole story: the two inbound types are 68.6% of it.** `SIDE_INBOUND` is beyond 10 units on **99.5% of its steps** — essentially always. DREB, which I would have guessed at, is **zero**. HCT and FCP are near-zero. The rest of this report drops everything except the inbounds and the fast breaks.

### The phase table, per family (sim, `SD=1`)

| family | step | n | → bh(N−1) | → bh(N) | → bh(N+1) | winner | beyond 10 |
|---|---|---|---|---|---|---|---|
| **BASELINE_INBOUND** | 2 | 2,416 | **19.56** | 26.47 | 26.02 | N−1 "lag" | 99% |
| **BASELINE_INBOUND** | 3 | 2,296 | **25.96** | **25.96** | 16.98 | N+1 "lead" | 98% |
| **SIDE_INBOUND** | 2 | 1,660 | **22.58** | **22.58** | 14.00 | N+1 "lead" | 100% |
| FAST_BREAK/covert_release | 2 | 135 | 11.75 | 16.46 | 17.74 | N−1 | 47% |
| FAST_BREAK/covert_release | 3 | 75 | 17.76 | 19.70 | 19.44 | N−1 | 65% |
| FAST_BREAK/rim_runner | 2 | 160 | 3.62 | 7.55 | 19.45 | N−1 | 15% |
| FAST_BREAK/rim_runner | 3 | 101 | 11.34 | 17.09 | 20.78 | N−1 | 52% |
| FCP | 3 | 944 | 4.39 | **3.93** | 6.31 | N — ok | 12% |
| HCT | 3 | 896 | 9.12 | **2.67** | 5.19 | N — ok | 1% |
| HCO | 3 | 4,738 | 18.28 | **3.79** | 5.62 | N — ok | 2% |

**Look at the bolded ties.** `BASELINE_INBOUND` step 3 is **25.96 vs 25.96** and `SIDE_INBOUND` step 2 is **22.58 vs 22.58** — identical to two decimal places, across thousands of steps. That is not a near-miss; it is the same measurement twice, because the ball handler is in the same place at N−1 and N. The `played` arm reproduces every row to within ~1.5 units, and `SD=0` matches both.

## Step 2 — is the ball simply moving far? For inbounds, it is worse than that: it is not moving at all, and it is off the court

### The ball handler on an inbound (n=40, sim, `SD=1`; probe 40/40)

| family \| step | steps | **ball handler out of bounds** | **frozen vs the previous step** |
|---|---|---|---|
| **SIDE_INBOUND \| 1** | 1,660 | **100.0%** | n/a |
| **SIDE_INBOUND \| 2** | 1,660 | **100.0%** | **100.0%** |
| SIDE_INBOUND \| 3 | 1,660 | 0.4% | 0.0% |
| BASELINE_INBOUND \| 1 | 2,416 | 5.1% | n/a |
| **BASELINE_INBOUND \| 2** | 2,416 | **100.0%** | 5.0% |
| **BASELINE_INBOUND \| 3** | 2,416 | **95.0%** | **95.0%** |
| BASELINE_INBOUND \| 4 | 2,296 | 0.5% | 0.0% |
| HCO \| 2 | 4,778 | 0.6% | 5.7% |
| DREB \| 1 | 1,767 | 0.1% | n/a |

(Out of bounds = outside the playable area the engine uses elsewhere, x 3–97 / y 3–47.)

### How much of the apparent lag is just the ball handler moving?

`gap = d(defenders@N → bh(N−1)) − d(defenders@N → bh(N))`. Negative means defenders sit nearer where the ball *was* — the argmin "lag". **`|gap| / BH moved`** is the share of the ball handler's own movement the defenders did **not** follow: ~1.0 means they stayed put, ~0.0 means they tracked him step for step.

| family \| step | n | BH moved | gap | **unfollowed** | reading |
|---|---|---|---|---|---|
| **BASELINE_INBOUND \| 2** | 2,416 | 7.8 | −6.91 | **89%** | the ball handler walked **out of bounds**; the defence stayed on the court |
| **BASELINE_INBOUND \| 3** | 2,296 | **0.0** | 0.00 | n/a | **stationary** — the comparison is degenerate |
| **SIDE_INBOUND \| 2** | 1,660 | **0.0** | 0.00 | n/a | **stationary** — the comparison is degenerate |
| FAST_BREAK/covert_release \| 2 | 135 | 41.7 | −4.71 | **11%** | defenders chased and closed most of it |
| FAST_BREAK/rim_runner \| 3 | 101 | 40.3 | −5.75 | **14%** | defenders chased and closed most of it |
| FAST_BREAK/rim_runner \| 2 | 160 | 22.4 | −3.93 | 18% | chased; also 100% a pass, so the handler changed |
| FAST_BREAK/rim_runner \| 4 | 67 | 23.2 | −1.48 | **6%** | chased and nearly kept pace |
| FAST_BREAK/covert_release \| 3 | 75 | 4.2 | −1.94 | 46% | small absolute gap (1.9 units) on a 4.2-unit move |
| FAST_BREAK/rim_runner \| 5+ | 35 | 5.9 | −2.30 | 39% | small absolute gap on a small move, n=35 |
| FCP \| 3 | 944 | 13.9 | +0.45 | 3% | handler ran *at* the defence |
| HCO \| 3 | 4,738 | 17.0 | +14.49 | 85% | handler ran *at* the defence |

**The two inbound rows that produce the whole effect are `0.0` and `−6.91 on a 7.8-unit walk out of bounds`.** There is nothing for a defender to be late for.

**On the fast breaks the defenders are the opposite of lagging** — they fail to follow only 6–18% of a 20–42 unit sprint on every bucket with meaningful n. Being 12–20 units behind the ball on a fast break is what a fast break *is*. The two buckets with a higher unfollowed share (covert_release step 3 at 46%, rim_runner 5+ at 39%) are small absolute gaps — 1.9 and 2.3 units — on small moves, at n=75 and n=35. I would not call those anything.

**A methodological note I owe you.** My first cut at this statistic was a "closure" ratio that I had to throw away: it was defined so that a negative gap produced a value above 1.0, which read as "defenders more than kept up" when it actually meant the opposite. I caught it before it reached this report, but it would have inverted the fast-break conclusion. The table above is the reworked version — plain gap, plain ratio, sign stated.

## Step 3 — not reached

Per the brief's stopping rule, the answer at Step 2 is **"the ball handler is stationary and out of bounds, and the defence is correctly not near him."** No builder or emitter is at fault, so there is no code path to name. The `bip_passer_hold` / `sip_passer_hold` steps below are doing exactly what their names say.

## Trace — 6 inbound turns, first four steps (sim, `SD=1`, seed 8000; probe 40/40)

```
### SIDE_INBOUND  (3 steps each)

-- turn 1 --
 step 1  BH f608a824 at [53.0, 48.0]   reason=sip_setup_walkin        <- y=48, OUT OF BOUNDS
     PF [20.0,25.0] guard_offball d=40.22    PG [40.0,25.0] guard_offball d=26.42
     SF [34.0,17.0] guard_offball d=36.36    C  [15.0,28.0] guard_offball d=42.94
     SG [36.0,33.0] guard_offball d=22.67
 step 2  BH f608a824 at [53.0, 48.0]   reason=sip_passer_hold         <- IDENTICAL position
     all five defenders: IDENTICAL coords, action=stationary, same distances
 step 3  BH 104c7b0f at [49.0, 42.0]   reason=sip_inbound_pass        <- ball comes inbounds
     PF d=33.62   PG d=19.24   SF d=29.15   C d=36.77   SG d=15.81    (defenders unmoved)

-- turn 2 (mirror end) --
 step 1  BH 9c044323 at [47.0, 48.0]   sip_setup_walkin   defenders 22.67-42.94 away
 step 2  BH 9c044323 at [47.0, 48.0]   sip_passer_hold    identical, all stationary
 step 3  BH c13c8088 at [50.0, 37.0]   sip_inbound_pass   SG now 14.56, PG 15.62

### BASELINE_INBOUND  (4 steps each)

-- turn 1 --
 step 1  BH f608a824 at [90.0, 25.0]   reason=bip_sf_to_rim      defenders 5.19-7.98  <- CLOSE
 step 2  BH f608a824 at [97.0, 25.0]   reason=bip_sf_to_inbound  defenders 18.38-20.97
                                        ^ he walked 7 units to x=97, BEHIND THE BASELINE
 step 3  BH f608a824 at [97.0, 25.0]   reason=bip_passer_hold    identical, all stationary
 step 4  BH 104c7b0f at [90.0, 25.0]   reason=bip_inbound_pass   defenders 18.05-21.61

-- turn 3 --
 step 1  BH 9c044323 at [10.0, 25.0]   bip_sf_to_rim        defenders 11.03-26.17
 step 2  BH 9c044323 at [ 3.0, 25.0]   bip_sf_to_inbound    defenders 41.23-58.51
 step 3  BH 9c044323 at [ 3.0, 25.0]   bip_passer_hold      identical, all stationary
 step 4  BH c13c8088 at [10.0, 25.0]   bip_inbound_pass     defenders 40.00-54.12
```

**Read turn 1 of BASELINE_INBOUND.** At step 1 the defenders are **5.2–8.0 units** away — tight coverage. Then the inbounder walks to **x = 97**, behind the baseline, and the distance becomes 18–21. Nothing moved wrongly; a man stepped out of play and the defence stayed in it. Step 3 is `bip_passer_hold` — every defender `stationary`, every coordinate identical to step 2, which is why `d(N−1)` and `d(N)` come out equal to two decimals across 2,296 steps.

Turn 3 is the extreme version: the inbounder is at x = 3 and the defence has already retreated to x = 44–60 to set up against the *next* possession, 41–58 units away. That looks alarming on a distance table and is entirely correct.

## Sim vs played

Identical. Every row of the phase table matches within ~1.5 units, the unfollowed shares match within 2–4 pp, and `SD=0` reproduces both. This is not an arm-parity issue.

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039, `SEED_DEFENSES=1` and `=0`, both arms. **sim arm** = `_is_full_simulation` True throughout; **played arm** = False only inside the four gated Animator methods at Pattern A. All probes hook `sync_lineup_coords_from_turn`, so they read the **final** `animation_steps` for every turn type. Defenders are the lineup of the team that is not `turn_result["offense_team_id"]`, so a possession flip before the sync cannot mislabel them. The out-of-bounds/frozen table and the trace are sim `SD=1`, n=40 and 1 seed respectively, labelled as such.

## What this corrects

`reports/defender-phase-2026-09-20.md` §2 said: *"THERE IS a genuine phase lag — but on the other turn families... at step 2 defenders are 14.08 from where the ball handler WAS and 16.89 from where he IS."* **That was an artefact of a single pooled "other" bucket**, dominated by inbounds where the two quantities are the same number. The correction does not touch that report's HCO findings, which stand: HCO is in phase at every step index, HCO step 1's gap is transition geometry, and `guard_ball` is essentially never tagged on HCO. **That last one remains the only real defect found in either pass.**

## Not covered

- **No engine code changed, no fix built.** No flags, nothing retuned.
- **Not investigated:** the `guard_offball` / `stationary` tagging on inbound steps. The trace shows all five defenders tagged `stationary` on `sip_inbound_pass` while the ball is in flight, which may or may not be what the renderer wants — it is the same tagging family as the HCO `guard_ball` gap and belongs with it, not here.
- **Not resolved:** the two small fast-break buckets (`covert_release` step 3, `rim_runner` 5+) where 39–46% of a small movement is unfollowed. Absolute gaps of 1.9–2.3 units at n=35–75. Too small to call, not chased further.
- **Not checked:** whether `BASELINE_INBOUND` step 1's 5.1% out-of-bounds rate (against 100% at step 2) means anything — it is the step before the inbounder walks out, so it is probably just players near the baseline.
