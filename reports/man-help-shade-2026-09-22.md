# The man weak-side help shade, behind `GOB_MAN_HELP_SHADE` (default OFF)

**Yes — the weak-side helper now protects the rim.** With the flag on, the weak-side off-ball
defender ends up 13.25 → **10.71** from the basket at posture normal (played arm 13.15 → 10.63),
and more of his added movement is rim-ward than ball-ward (+1.52 along man→rim vs +0.94 along
man→ball). That is the rim protection Loose was supposed to buy and never did.

**Yes — the strong side is untouched.** Strong-side defender→rim moves 15.24 → **14.94** (−0.30)
and his gap to his man 6.29 → 6.57 (+0.28). That is the whole point of the shape: the flat bump
to 0.40 would have dragged him to 11.65 with a gap of 9.56. The `HELP_ANCHOR_FLOOR` bind rate
does **not** rise — it falls slightly, 27.3% → 25.8%.

**Almost nothing moves on the scoreboard.** Points per team −0.06 ±2.10 at normal and +0.53 ±1.87
at loose. Three differences clear their own CI: at normal the defence loses steals
(−1.11 ±0.88), and at loose the offence is pushed out of the paint and into threes
(paint −1.25 ±1.16, 3PA +1.16 ±1.13). Everything else is flat.

---

## 1. What was built

`GOB_MAN_HELP_SHADE`, **default `"0"`**, in the man off-ball help branch of
`_apply_defender_posture` ([shared_defense.py:2048-2087](BackEnd/utils/shared_defense.py#L2048-L2087)).
Commit `0c5e9ae38`; tests `383fbe22b`.

```
effective shade = HELP_BASKET_SHADE * (1 + weakness)
```

- **weakness** comes from `help_side_weakness`, which was **extracted** from
  `_apply_zone_help_shade` — the zone shade now calls it too, so there is one ramp
  (`zone_sink.SIDE_SPAN` + `ball_centrality`), not a second copy. That extraction is
  behaviour-preserving arithmetic.
- Strong side and a **central ball** are unchanged (weakness 0 → 0.20). Far weak side doubles
  (→ 0.40).
- **Untouched:** deny/tight, the inside-man lock, the on-ball cushion. **No clamp.** **No
  constant retuned.** `GOB_BOXOUT_CONTEST` still defaults `"0"`.

### Flag OFF does not move the reference

`equiv_v3_reference_32db56c77_helpshade` reproduces on **fingerprint AND draws**:

| cell | sim | played |
|---|---|---|
| `SEED_DEFENSES=1` | 40/40 | 40/40 |
| `SEED_DEFENSES=0` | 40/40 | 40/40 |

**160/160.** No re-cut. Those runs have the zone shade ON by default, so they also prove the
`help_side_weakness` extraction changed nothing.

---

## 2. Tests — `tests/test_man_help_shade_flags.py` (16 tests)

Default OFF; the flag turns it on; **flag-off returns the constant itself**; OFF and ON agree
exactly on the strong side; weak side moves toward the **defended** rim; away offense uses the
mirrored rim; a central ball gets no extra shade; the far weak side doubles; **`HELP_BASKET_SHADE`
is reused not copied** (doubling it doubles the shade) and so is the ramp (widening `SIDE_SPAN`
shrinks it); **one ramp serves both shades** (neutralise `help_side_weakness` and the zone shade
AND the man shade both fall back); deny, the inside-man lock and the on-ball cushion are
unaffected; no clamp in the signature; every posture constant is still at its shipped value.

Suite: **3191 passed, 20 skipped, 112 xfailed, 0 failed, 0 XPASS** at the default **and** with
`GOB_MAN_HELP_SHADE=1`.

---

## 3. Geometry, OFF vs ON (n=40, seeds 8000-8039, SD=1, sim arm)

Played arm agrees within ±0.1 on every number; both arms are in the table below where they differ.

### Normal

| metric | OFF (mean/p50/p90) | ON (mean/p50/p90) | Δ mean |
|---|---|---|---|
| defender → rim | 14.58 / 14.90 / 19.30 | **13.29** / 13.40 / 19.20 | **−1.30** |
| gap to man | 7.77 / 7.10 / 12.00 | 9.20 / 9.10 / 15.00 | +1.44 |
| distance to ball | 14.85 / 14.00 / 21.60 | 14.31 / 13.90 / 20.00 | −0.54 |
| sag along man→**rim** | 6.57 | 8.09 | **+1.52** |
| sag along man→**ball** | 6.48 | 7.42 | +0.94 |

| by ball side | share | defender → rim | gap to man |
|---|---|---|---|
| strong (incl. central ball) | 54% | 15.24 → **14.94** (−0.30) | 6.29 → 6.57 (+0.28) |
| middle | 17% | 14.71 → 12.58 (−2.13) | 8.12 → 9.97 (+1.85) |
| weak | 29% | 13.25 → **10.71** (−2.55) | 10.36 → 13.51 (+3.16) |

`HELP_ANCHOR_FLOOR` binds: **27.3% → 25.8%** (x 16.3→15.2, y 11.0→10.7, both 0.0→0.0).
Played arm: 28.3% → 26.3%.

### Loose

| metric | OFF | ON | Δ mean |
|---|---|---|---|
| defender → rim | 14.24 | **13.43** | −0.81 |
| gap to man | 11.56 | 12.97 | +1.42 |
| distance to ball | 11.25 | 11.10 | −0.15 |
| sag along man→rim | 8.74 | 10.32 | +1.57 |
| sag along man→ball | 10.45 | 11.41 | +0.95 |

| by ball side | defender → rim | gap to man |
|---|---|---|
| strong | 15.16 → **14.81** (−0.35) | 9.10 → 9.37 (+0.27) |
| middle | 12.99 → 11.48 (−1.51) | 11.69 → 13.42 (+1.73) |
| weak | 13.28 → **12.03** (−1.24) | 16.07 → 19.21 (+3.14) |

`HELP_ANCHOR_FLOOR` binds: 26.6% → 26.4%.

### Deny — byte-for-byte unchanged

Every number identical to three decimals, on both arms: gap 2.09, rim 19.81, passing lane 99.7%.
The shade counter registers 112 calls out of 194,569 (non-HCO stragglers that carry a help
posture), 16 of them shaded — 0.008%. **Deny is not touched.**

### Health

| check | OFF | ON |
|---|---|---|
| same-moment gate (normal) | 68,715 / 68,715 = **100%**, max 0.000 | 69,715 / 69,715 = **100%**, max 0.000 |
| same-moment gate (loose) | 68,275 / 68,275 = **100%**, max 0.000 | 68,000 / 68,000 = **100%**, max 0.000 |
| §8.1 continuity corrections | **0** of 1,934 / 1,889 calls | **0** of 1,873 / 1,905 calls |
| census errors | 0 | 0 |
| worker errors (480 games) | 0 | 0 |

Freeze-miss per game (n=40, paired): normal sim −0.33 ±0.75, normal played −0.28 ±0.75, loose sim
−0.07 ±0.51, loose played +0.45 ±0.49, deny +0.00 ±0.00. **Nothing clears its CI.**

### The two questions, answered

**Does ON give the weak-side helper the rim protection Loose was supposed to buy, without moving
the strong side? Yes.** Weak-side rim distance falls 2.55 at normal and 1.24 at loose, the strong
side moves 0.30-0.35, and the added movement is predominantly rim-ward (+1.52 vs +0.94). The
measured weak-side result (10.71) lands where the counterfactual said it would (10.52).

**Does Loose now differ from Normal in the rim axis, not just the ball axis? No.** With the flag
on, defender→rim is 13.29 at normal and **13.43** at loose — loose is still, marginally, the
*further* of the two. On the weak side it is starker: normal 10.71 vs loose 12.03. The shade
scales with ball side, not with posture, so it lifts both postures and leaves the gap between
them exactly where it was. Loose still buys ball-ward float relative to Normal. **That is the
case for item 7 below, and it is Jamie's second decision, not this build's.**

---

## 4. Outcomes, seed-paired (n=120, seeds 8000-8119, played arm, SD=1)

CI = 1.96 × SEM of the **per-seed difference**.

### Posture normal

| metric | OFF | ON | ON − OFF |
|---|---|---|---|
| points / team | 73.57 ±1.79 | 73.51 ±1.75 | −0.06 ±2.10 |
| possessions | 40.91 ±1.10 | 39.66 ±1.16 | −1.25 ±1.40 |
| FG% | 40.29 ±1.14 | 40.77 ±1.12 | +0.48 ±1.22 |
| 3PA share | 35.36 ±0.90 | 35.86 ±0.89 | +0.50 ±1.27 |
| paint share | 29.05 ±0.87 | 29.08 ±0.87 | +0.03 ±1.17 |
| **steals** | 17.47 ±0.66 | 16.36 ±0.68 | **−1.11 ±0.88** |
| deflections | 8.96 ±0.50 | 8.78 ±0.58 | −0.18 ±0.69 |
| blocks | 10.14 ±0.54 | 9.86 ±0.60 | −0.28 ±0.80 |
| fouls | 31.13 ±1.07 | 30.98 ±1.14 | −0.15 ±1.28 |
| freeze-miss | 2.43 ±0.29 | 2.14 ±0.26 | −0.29 ±0.40 |

### Posture loose

| metric | OFF | ON | ON − OFF |
|---|---|---|---|
| points / team | 75.63 ±1.89 | 76.16 ±1.54 | +0.53 ±1.87 |
| possessions | 39.61 ±1.11 | 38.74 ±1.04 | −0.87 ±1.28 |
| FG% | 40.79 ±1.18 | 41.50 ±1.20 | +0.71 ±1.21 |
| **3PA share** | 36.10 ±0.95 | 37.25 ±0.97 | **+1.16 ±1.13** |
| **paint share** | 28.91 ±0.86 | 27.67 ±0.88 | **−1.25 ±1.16** |
| steals | 17.64 ±0.78 | 17.32 ±0.72 | −0.33 ±1.07 |
| deflections | 9.21 ±0.54 | 9.12 ±0.50 | −0.08 ±0.69 |
| blocks | 9.47 ±0.57 | 9.38 ±0.56 | −0.08 ±0.75 |
| fouls | 32.92 ±1.07 | 32.36 ±1.17 | −0.57 ±1.37 |
| freeze-miss | 1.93 ±0.24 | 2.11 ±0.25 | +0.17 ±0.33 |

**What resolves.** Three things, and they are the three you would predict from the geometry:

- **normal: steals −1.11.** The helper stands further off his man, so he arrives at fewer
  passes. This is the price of help defence and it is a real cost, not noise.
- **loose: paint share −1.25 and 3PA +1.16.** With the weak side actually protecting the rim, the
  offence takes the shot the defence concedes. The two move together and roughly cancel in points.

**What does not.** Points per team, possessions, FGA, FG%, deflections, blocks, fouls and
freeze-miss, at both postures. **Nothing was retuned to chase any of these.**

---

## 5. Pictures

| | |
|---|---|
| [man-help-shade-off-normal](reports/man-help-shade-off-normal-2026-09-22.png) | [man-help-shade-on-normal](reports/man-help-shade-on-normal-2026-09-22.png) |
| [man-help-shade-off-loose](reports/man-help-shade-off-loose-2026-09-22.png) | [man-help-shade-on-loose](reports/man-help-shade-on-loose-2026-09-22.png) |

The OFF and ON figures show **the same four steps**, same seeds, same axes. Both placements are
recomputed from that step's own man/ball/rim with the jitter pinned to 0, so the *only* difference
between the two figures is the flag. (The ON game diverges from the OFF game as soon as the first
shaded placement changes a contest, so sampling each run separately would not have been the same
step at all.) The recomputation is representative: it predicts a weak-side rim distance of 10.52
at normal and 12.13 at loose; the real ON runs measured **10.71** and **12.03**.

Panels are the closest-to-pooled-median steps, one per seed — typical, not extreme — **drawn from
the steps that have at least one man off the strong side** (271 of 365 at normal, 317 of 423 at
loose). The first cut did not filter, and all four loose panels came out with a central ball, so
the two figures were pixel-identical: **a central ball produces no shade at all, by design.** That
is not rare — it is 25.1% of off-ball calls at normal and 25.7% at loose. Worth knowing before the
eye test: on a quarter of placements this change does nothing whatsoever.

In the loose pair, watch the far-side men: seed 8008's weak-side gaps go 15.3 → 18.2 and 16.8 →
18.9 while the man beside the ball stays at 7.6 → 7.6, and the panel's mean defender→rim drops
11.2 → 10.1.

---

## 6. See it in staging

1. **Railway** → the staging service → Variables → add `GOB_MAN_HELP_SHADE` = `1`, redeploy.
   (Remove it or set `0` to roll straight back; nothing else changes.)
2. Start a game as the **defending** team.
3. In the **Playcall Center**, find the **Defense card** (it reads "Man Normal" by default).
4. Arrow up/down to **Loose Man**, then click the card to select it.
5. It stays set every possession until the red **X** clears it.

Watch the two men furthest from the ball. With the flag off they drift toward the ball and leave
the basket open behind them; with it on they slide down into the lane while the man next to the
ball barely moves.

---

## 7. Should posture scale the shade too? The case, and what it costs

**The case.** §3 answered "no" to the second question: with the flag on, Loose is still no more
rim-protective than Normal (13.43 vs 13.29 overall; 12.03 vs 10.71 on the weak side). If "loose"
is meant to mean "helping harder", it should shade harder, not only sag further toward the ball.

**What it would cost.** Priced from the OFF samples (seeds 8000-8009, 33,872 placements; pure
arithmetic, jitter pinned to 0 in every variant). `R` = `HELP_SAG[posture] / HELP_SAG["normal"]`
= 1.83 at loose, 1.00 at normal, so nothing below changes posture normal at all.

| variant, at posture **loose** | defender→rim strong / middle / weak | gap to man strong / middle / weak |
|---|---|---|
| flag OFF (0.20 flat) | 15.28 / 13.00 / 13.32 | 8.93 / 11.70 / 16.18 |
| **flag ON as built** `0.20 × (1+w)` | 14.93 / 11.23 / 12.13 | 9.27 / 13.73 / 19.15 |
| posture × the **whole** shade `0.20 × (1+w) × R` | **11.93** / 7.45 / 11.12 | **11.87** / 18.67 / 24.96 |
| posture × the **weak term** `0.20 × (1+w×R)` | 14.56 / 10.05 / 11.42 | 9.53 / 15.20 / 21.77 |

- Scaling the **whole** shade is the flat-bump mistake again: the strong-side defender goes
  15.28 → 11.93 and his gap 8.93 → 11.87, and the middle band ends up at 7.45 — inside the paint
  with a man on the perimeter. **Do not do this one.**
- Scaling only the **weak term** keeps the strong side (15.28 → 14.56) and buys a further 0.71 on
  the weak side (12.13 → 11.42). It is the shape-correct version.
- Even so it does **not** make Loose more rim-protective than Normal (11.42 vs 10.52) — at loose
  the ball-ward sag is large enough that the shade cannot fully offset it. If the goal is "Loose
  protects the rim more than Normal", the lever is `HELP_SAG` itself, not the shade.

Not built. Jamie's decision.

---

## Tunable Constants

Reported, not changed. Nothing was retuned to build this.

| constant | value | effect | what this measurement says |
|---|---|---|---|
| `MAN_HELP_SHADE_FLAG` (`GOB_MAN_HELP_SHADE`) | `"0"` | gates the weak-side scaling | built and measured; **not flipped** |
| `HELP_BASKET_SHADE` | 0.20 | fraction of man→basket added to the help spot | now the *base* of the scaled term; reused, not copied |
| the scale | `1 + weakness` | 1.0 strong / central, 2.0 far weak side | weak-side rim 13.25 → 10.71, strong side −0.30 |
| `zone_sink.SIDE_SPAN` | 30.0 | the strong/weak ramp | shared with the zone shade via `help_side_weakness` |
| `zone_sink.CENTRALITY_PLATEAU` | (23.0, 28.0) | central ball ⇒ no weak side | 25.1% / 25.7% of calls get no shade |
| `HELP_SAG` | normal 0.30 / loose 0.55 | fraction of the way toward the **ball** | untouched; still the only posture-sensitive term, hence §7 |
| `HELP_ANCHOR_FLOOR` | 0.30 | min follow in the basket-aligned axis | bind rate **falls** 27.3% → 25.8%; the shade does not press on it |
| `HELP_SAG_JITTER` | 0.10 | ±0-10% on the sag | pinned to 0 in the counterfactuals and the pictures only |
| `POSTURE_DENY_DISTANCE` | 2.0 | off-ball deny | untouched; deny identical to three decimals |
| `GOB_BOXOUT_CONTEST` | `"0"` | unrelated | still off in the tree |

---

## Footing

equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed-8000)`. **`SEED_DEFENSES=1` for every measurement** (production footing: the six
real defenses are seeded, so zone calls play as zone); the reference reproduction covers
`SEED_DEFENSES` 1 and 0, sim and played. Posture set through `EQUIV_MAN_POSTURE` (`de8cf1c92`),
which writes the teams' playbook `man_defense` % — the same path a user's saved playbook uses.
Geometry n=40 (seeds 8000-8039), both arms. Outcomes n=120 (seeds 8000-8119), played arm.
CI = 1.96 × SEM. sim arm = `_is_full_simulation` True throughout; played arm = False only inside
the four gated Animator methods at Pattern A. 800 measurement games + 160 reproduction games +
80 probe games, 0 errors.

The off-ball census wraps `_apply_defender_posture`, calls the original first, and only reads its
inputs and its return value — it draws nothing. Proved, not asserted: the 160/160 reproduction
above ran with the census **on**.

**Not flipped. Not merged.**
