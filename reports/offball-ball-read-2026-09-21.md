# Off-ball defenders and the ball: measured

**Forwarding `ball_spot` fixes neither #1 nor #3.** For the zone defender with an empty area (#1) the
caller never supplies a ball spot in the first place and the placement does not even go through that
function; for man off-ball (#3) the posture layer already reads the real ball coordinates and
overrides the branch entirely, so forwarding moves those defenders **0.0 %** of the time.

What forwarding *does* move is two things nobody complained about: the **post/inside** man matchups
(50.7 % of them, mean 5.20 grid units) and the **drive reconstruction** (86 %). Both are real, neither
is the complaint.

Read-only. **No code changed** — `git diff` is 0 lines against `c79520ae3`, the only new files are
this report and three PNGs. `GOB_BOXOUT_CONTEST` still `"0"`, nothing retuned.

---

## 0. Sync and verification

`develop` merged into `feature/animation-reward` — a fast-forward to **`c79520ae3`**. develop's 26
commits are training, persistence and loopback work; the only `BackEnd/engine|models` files they touch
are `franchise_manager.py` and `training_execution_v2.py`, neither on the sim path.

**The current reference still holds. n=40, both arms, both footings:**

| cell | fingerprint | draws | errors |
|---|---|---|---|
| sim SD=1 | **40/40** | **40/40** | 0 |
| sim SD=0 | **40/40** | **40/40** | 0 |
| played SD=1 | **40/40** | **40/40** | 0 |
| played SD=0 | **40/40** | **40/40** | 0 |

*(36 untracked `READY--*.md` files blocked the merge because develop tracks them. I moved mine aside,
merged, restored, then compared: **all 36 byte-identical**, nothing lost.)*

## 1. The root, re-found at the current tree

`BackEnd/utils/shared_defense.py`:

| line | what |
|---|---|
| **2004** | `get_defender_coords(..., ball_spot: str = None, ...)` — accepted, documented *"For non-BH defenders: ball handler's spot"* |
| **2084–2091** | `calculate_defender_coords(offensive_coords_home, target_basket, aggression_level, spot, ball_handler_coords_home, is_ball_handler)` — **six positional args. `ball_spot` is the seventh parameter and is not passed.** |
| **1762** | `ball_spot_used = ball_spot if ball_spot else "key"` |
| **1767** | `if ball_spot_used == "key":` — the branch that therefore always runs |

**`ball_spot` appears exactly once in the body of `get_defender_coords`: in the signature.** The root
is confirmed and unchanged by the freeze work.

**But "ball position is not an input" is too strong, and the distinction matters.** Inside the `"key"`
branch the defender is still placed off the **real ball coordinates** — `bx, by` come from
`ball_handler_coords`, and `x_direction = 1 if bx > ox else -1`. What is frozen is the **branch
selection**, not the ball. Every off-ball defender is placed by the *key-relative formula* even when
the ball is in the corner.

### What each off-ball path actually uses as "the ball"

| path | reference point | is `ball_spot` even supplied? |
|---|---|---|
| **man off-ball, outside spots** | `_apply_defender_posture` (`:1955`), which takes **real ball coords** and adds a basket shade — and **replaces** the aggression result at `:2126` | supplied, but the value it feeds is discarded |
| **man off-ball, post/inside spots** | the aggression base survives (`_POSTURE_INSIDE_SPOTS` returns early at `:1971`), so the `"key"` formula stands | supplied, and dropped |
| **zone off-ball (man in the area)** | the `"key"` formula, on real ball coords | **never supplied — `None` on 100 % of calls** |
| **zone, empty area** | `zone_sink.sink_position` — **returns at `:986` without calling `get_defender_coords` at all** | n/a |
| **drive reconstruction** | the `"key"` formula | supplied, and dropped |

## 2. The path census

sim SD=1, n=40 games, **22,308 off-ball `get_defender_coords` calls per game**, plus **6,564
empty-zone placements per game** that bypass it entirely.

| off-ball path | calls/game | `ball_spot` supplied | **moved by forwarding** | displacement when it moves (mean / p50 / p90 / max) |
|---|---|---|---|---|
| **ZONE off-ball** | 17,125 | **0 % — always `None`** | **0.0 %** | — |
| **MAN outside (posture governs)** | 3,582 | 100 % | **0.0 %** | — |
| MAN post/inside (posture bypassed) | 1,381 | 100 % | **50.7 %** | 5.20 / 4.47 / 10.00 / 13.00 |
| DRIVE reconstruction | 220 | 100 % | **86.0 %** | 5.27 / 5.00 / 9.22 / 15.03 |
| *(empty-zone sink — separate path)* | *6,564* | *n/a* | *n/a* | *see §4* |

**Method note, because it changed the answer.** The counterfactual recomputes the same call twice on
an *isolated* RNG at the **same seed** — once with `ball_spot` dropped, once forwarded — so the
displacement is the branch change and not jitter. My first pass did not pin the posture sag jitter,
and because the two branches consume different numbers of `randint`s upstream the downstream posture
draw fell out of phase; that reported **6.8 %** movement on man outside spots which is really **0.0 %**.
The figure above is with `HELP_SAG_JITTER` pinned to 0 for both recomputes. Neither recompute touches
`sim_rng`.

## 3. Answering #3 — man help distance

**Forwarding does nothing here.** `_apply_defender_posture` computes the full position from man, ball
and basket and returns it, discarding the aggression base for every non-inside spot. Measured: **0 of
143,280 man-outside off-ball placements move.**

Where those defenders actually stand today (posture `normal`):

| path | to ASSIGNMENT | to BALL | to RIM |
|---|---|---|---|
| **MAN outside** | mean **7.68** p50 7.07 p90 12.04 | 14.73 / 14.04 / 21.38 | 14.66 / 14.87 / 19.31 |
| MAN post/inside | 5.04 / 4.00 / 9.22 | 18.85 / 19.85 / 24.33 | 7.03 / 7.21 / 9.90 |
| ZONE off-ball | 7.90 / 7.62 / 13.15 | 16.54 / 16.26 / 24.33 | 13.05 / 12.53 / 23.00 |

**The remainder is constants, not a missing input and not a missing branch.** The help spot is
`HELP_SAG` of the way from man toward ball plus `HELP_BASKET_SHADE` toward the rim, anchored per axis
with `HELP_ANCHOR_FLOOR`. All three are live and all three already read the ball. If 7.68 units is too
close, the lever is `HELP_SAG` (0.30) and `HELP_ANCHOR_FLOOR` (0.30), which hold him near his man in
the basket-aligned axis. **Reported, not changed.**

**One thing I could not measure: man loose and man deny never occur in this fixture.** Across 892,334
off-ball calls the only postures seen are `None` and `normal`. Jamie's #3 names *normal and loose*; I
can measure normal and I can say that loose runs the identical code path with `HELP_SAG` 0.55 instead
of 0.30 — but I have not observed it, and I am not going to report a number for it.

## 4. Answering #1 — zone anchoring

**Two separate reasons forwarding cannot help.** The zone caller supplies `ball_spot=None` on 100 % of
its 17,125 calls per game, so there is nothing to forward; and the defender Jamie is describing — the
one with *no offender in his area* — does not call `get_defender_coords` at all. He is placed by
`zone_sink.sink_position`, which already reads the ball **and** the rim.

**Where he ends up** (6,564 placements/game, n=40):

| | anchor | final | change |
|---|---|---|---|
| distance to RIM | 14.33 | **12.31** | 2.03 closer (p50 1.87) |
| distance to BALL | 18.78 | 16.11 | 2.67 closer |
| movement from anchor | — | mean 4.02, p50 3.94, p90 6.96, **max 8.00** |

**What is holding him out there — and it is not the ball pull:**

| limiter | share |
|---|---|
| **polygon clamp pulled him back** (`_clamp_into` keeps him inside his own zone) | **61.0 %** (mean pull-back 1.35) |
| **reach cap** hit (the role-class cap on total movement) | **35.7 %** |
| both | 35.7 % |
| neither — free to go where the pull wants | 39.0 % |

By role class:

| class | share | reach | rim: anchor → final | reach-capped | clamped |
|---|---|---|---|---|---|
| **perimeter** | 8.8 % | 8.0 | 20.94 → **16.31** | **57.7 %** | **85.0 %** |
| spanning | 61.9 % | 7.0 | 16.21 → 13.45 | 42.5 % | 62.2 % |
| interior | 29.3 % | 5.0 | 8.38 → **8.69** *(moves away)* | 14.9 % | 51.4 % |

**The weak-side rim weight is already 0.75** (`shape` preset, `basket_weak`). He is *already pulling
hard toward the basket* and being stopped: the perimeter-class defender — exactly the "stations too
far out on the perimeter" case — is **clamped 85 % of the time and reach-capped 58 %**. See
`offball-zone-empty-2026-09-21.png`: the green square is where the pull wants him, the red is where he
is allowed to stand.

**So #1 is a missing branch plus constants, not a missing input.** The branch is that the clamp has no
exception for sinking toward the rim — a zone defender is never permitted to leave his polygon even
when every weight says he should. The constants are `reach_perimeter` (8.0) and the clamp itself.
This matches conclusion 4 of `_documentation_master/projects/zone-d-placement.md`, reached
independently by code read on 2026-09-19.

**Zone off-ball with a man in the area is a third, separate thing** and the tabled doc is right about
it: 7.90 to assignment and 13.05 to rim, placed by the `"key"` formula with **no basket shade at all**
(the shade only exists in `_apply_defender_posture`, which zone never calls). That is a missing branch
too, and forwarding `ball_spot` would change the formula it uses but still not give it a basket shade.

## 5. Blast radius

This is outcome-moving work. Of the **35,004** placements per 40 games that forwarding would move
(3.9 % of all off-ball calls), the share that would cross the 11-unit contest radius:

| path | moved | cross the radius |
|---|---|---|
| MAN post/inside | 28,011 | 1,853 = **6.6 %** |
| DRIVE reconstruction | 6,993 | 1,162 = **16.6 %** |
| **total** | 35,004 | 3,015 = **8.6 %** |

Against *all* off-ball placements that is **0.34 %**. Proxy stated: distance to the **ball handler**,
not to a resolved shot spot — the probe does not carry the shot spot, so this is a stand-in for the
shot-contest geometry, and the interception/bat geometry reads the same stamped rows.

## 6. Pictures

| file | what it shows | how the steps were picked |
|---|---|---|
| `offball-man-normal-2026-09-21.png` | **no green markers anywhere** — forwarding moves nothing | median off-ball gap (7.91), four widely separated possessions |
| `offball-man-post-2026-09-21.png` | green arrows — the post case where forwarding *does* move him | median off-ball gap (7.73) |
| `offball-zone-empty-2026-09-21.png` | anchor ×, where the pull wants him (green), where he ends up (red), his polygon shaded | median final rim distance (11.89), one panel per role class |

Typical, not extreme: candidates are ranked by |value − median| and the four closest are taken, with a
minimum batch separation so the panels are four different situations rather than four frames of one.
**Man loose is absent** (§3), so the second figure shows the post case instead — it is where the
mechanism actually bites.

## 7. If the fix looks obvious — one paragraph, not a design

For **#1**, the smallest honest change is to let the sink leave its polygon toward the rim: either an
exception in `_clamp_into` for movement whose residual is rim-ward, or a per-class relaxation of
`reach_perimeter`. Cost: it is outcome-moving (the empty-zone defender is a real contest body), it
needs its own flag and a re-cut, and it risks defenders visibly standing in another zone's area, which
is the thing the clamp exists to prevent — so it wants Jamie's eye before it wants a number. For
**#3**, there is nothing to fix structurally; it is `HELP_SAG` and `HELP_ANCHOR_FLOOR`, and it belongs
in the single tuning pass. **Neither is built here.**

## 8. Footing and neutrality

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
n=40 seeds 8000–8039. **Catalogue-seeded state: `SEED_DEFENSES=1` throughout §2–§6 — zone only exists
there.** The §0 verification covers both arms and both footings.

| probe | cells | fingerprint | draws |
|---|---|---|---|
| post-merge verification | all four, n=40 | **40/40** | **40/40** |
| off-ball counterfactual | sim SD=1, n=40 | **40/40** | **40/40** |
| empty-zone sink | sim SD=1, n=40 | **40/40** | **40/40** |
| picture capture | sim SD=1, n=1 | ✓ | ✓ |

All probes read frame locals under `sys.monitoring`; the counterfactual runs on an isolated
`random.Random` with `shared_defense.random` swapped and restored, so it draws no `sim_rng`. **0 errors.**

*(`matplotlib` was installed into the untracked venv for the figures. No tracked file changed.)*

## 9. What I did not do

- **Built nothing.** No flags, no edits, nothing retuned.
- **Did not measure man loose or man deny** — absent from this fixture (§3).
- **Did not measure the legacy fallback branch** (`get_spacing`, the deny-tight 1–3 unit case the
  tabled doc flags) separately from the other `"key"`-branch cases; it needs its own tag.
- **Did not resolve the shot spot** for the blast radius — §5 uses the ball handler as a proxy and says so.
- **Did not touch the zone-with-a-man basket shade** beyond identifying it (§4).
- Did not run SD=0 for the counterfactual; zone does not exist there, so it would answer neither complaint.

## 10. Tunable constants — reported, not changed

| constant | where | value | bears on |
|---|---|---|---|
| `HELP_SAG` | `shared_defense.py:1937` | `{normal 0.30, loose 0.55}` | **#3** — how far toward the ball |
| `HELP_BASKET_SHADE` | `:1939` | `0.20` | #3 — rim shade (man only) |
| `HELP_ANCHOR_FLOOR` | `:1940` | `0.30` | **#3** — holds him near his man in the aligned axis |
| `HELP_SAG_JITTER` | `:1938` | `0.10` | — |
| `ONBALL_POSTURE_DIST` | `:1932` | `{tight 2.5, normal 3.5, loose 4.5}` | on-ball |
| `POSTURE_DENY_DISTANCE` | `:1934` | `2.0` | man deny off-ball |
| `WEIGHT_PRESETS["shape"]` | `zone_sink.py:102` | `ball 0.25/0.05, basket 0.15/**0.75**, reach 8/7/5` | **#1** — already rim-hungry |
| `INTERIOR_RIM_DISTANCE` / `PERIMETER_RIM_DISTANCE` | `zone_sink.py:60–61` | `12.0` / `20.0` | **#1** — role class, hence reach |
| `SIDE_SPAN` | `zone_sink.py:64` | `30.0` | #1 — strong/weak ramp |
| `CONTEST_EUCLIDEAN_RADIUS` | `constants/__init__.py:364` | `11` | §5 |
| `GOB_ZONE_SINK` / `GOB_ZONE_SINK_IQ` | | on / on | #1 |
