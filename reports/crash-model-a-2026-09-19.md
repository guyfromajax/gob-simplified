# Crash Model A — Stage 1: built, shown, stopped

## Step 0 — the reference debt is cleared

`equiv_v3_reference_1fd08c080_zonesink.json` only reproduced with `GOB_FOUL_ON_BALL_WEIGHT=0`, and that flag has been on by default since `4df7a87b4` — so nothing could be measured against the default tree. Re-cut at `d91679bef`, both arms, both footings, every shipped flag at its default:

| | sim | played | arm gap |
|---|---|---|---|
| `SEED_DEFENSES=1` | 71.83 ±3.25 | 73.21 ±2.39 | **−1.39 ±3.46** |
| `SEED_DEFENSES=0` | 74.31 ±3.57 | 75.74 ±3.25 | −1.43 ±3.72 |

Independence **PASS** on both arms and both footings; FT-honour windowed 99.5–99.6%; **0 errors in 160 games**.

| file | status |
|---|---|
| **`equiv_v3_reference_d91679bef_foulweight.json`** | **the reference from now on, for both arms** (`1b27fa95f`) |
| `equiv_v3_reference_1fd08c080_zonesink.json` | **superseded** — it describes a tree reachable only by forcing the foul flag off |
| earlier references | superseded, as previously recorded |

## The two-axis mismatch — and one result that argues against the obvious choice

Static sampling, 200,000 draws per cell, `|crasher destination − ball bounce|`:

| band | model | x med | x mean | x p90 | y med | y mean | y p90 | **euclid med** |
|---|---|---|---|---|---|---|---|---|
| 0–10 rim | TODAY | 2.0 | 2.5 | 5.0 | 4.0 | 4.0 | 8.0 | 5.0 |
| | **t=1.0** | 1.0 | 1.6 | 3.0 | 4.0 | 4.3 | 9.0 | 4.2 |
| | **t=0.7** | 1.0 | 1.5 | 3.0 | **3.0** | 3.7 | 8.0 | **4.0** |
| 10–18 short | TODAY | 2.0 | 2.5 | 5.0 | 4.0 | 4.0 | 8.0 | 5.0 |
| | **t=1.0** | 1.0 | 1.6 | 3.0 | 4.0 | 4.3 | 9.0 | 4.2 |
| | **t=0.7** | 1.0 | 1.5 | 3.0 | **3.0** | 3.8 | 8.0 | **4.0** |
| 18–26 mid | TODAY | 6.0 | 6.2 | 12.0 | 5.0 | 5.7 | 11.0 | 9.2 |
| | **t=1.0** | 3.0 | 4.0 | 8.0 | 6.0 | 7.0 | 14.0 | 8.2 |
| | **t=0.7** | 3.0 | 3.7 | 8.0 | 5.0 | 6.1 | 12.0 | **7.3** |
| 26–40 long | TODAY | 11.0 | 11.0 | 19.0 | 6.0 | 6.6 | 13.0 | 13.9 |
| | **t=1.0** | 5.0 | 6.0 | 12.0 | 7.0 | 8.3 | 17.0 | 11.0 |
| | **t=0.7** | 5.0 | 5.6 | 11.0 | 6.0 | 7.2 | 14.0 | **9.8** |
| 40+ deep | TODAY | **15.0** | 14.5 | 22.0 | 7.0 | 7.6 | 14.0 | **17.2** |
| | **t=1.0** | 6.0 | 6.3 | 13.0 | 8.0 | 9.7 | 20.0 | 12.1 |
| | **t=0.7** | **5.0** | 5.9 | 12.0 | 8.0 | 8.5 | 17.0 | **11.0** |

**The x axis does what the redesign was for.** Today's x error grows 2.0 → 15.0 across the bands (7.5×). Model A holds it at 1.0 → 5.0 (t=0.7) or 1.0 → 6.0 (t=1.0). **The growth flattens**, which was the stated target.

**The y axis is the result I did not expect, and it cuts against t=1.0.** Model A at t=1.0 is *slightly worse* than today on y in three of five bands (mid 6.0 vs 5.0, long 7.0 vs 6.0, deep 8.0 vs 7.0). The reason is not a bug: today's y box (20–30) is narrow and **already centred on the rim's y=25**, which is also the centre of the bounce distribution. A narrow guess at the mean beats a wide guess when you are scored on absolute error, even though the wide guess *covers* the right area. Today's y is correctly located and merely mis-scaled; today's x is badly located, which is why x improves so much and y does not.

**So "match the ball's spread exactly" is not the option that minimises distance to the ball — t=0.7 wins on every band and on both axes.** Euclidean median: 5.0 → **4.0**, 9.2 → **7.3**, 13.9 → **9.8**, 17.2 → **11.0**. Whether minimising that distance is even the right objective is Jamie's call: t=1.0 is the honest "crashers cover where the ball can go", t=0.7 is "crashers go where it probably goes". The pictures are the better basis for that decision than this table.

**The clamp never fires: 0.00% in all five bands**, at 20,000 draws each. It is a guard against a future band widening, not a live constraint — worth keeping, worth knowing it is inert.

## The pictures

**`reports/crash-model-a-visual-2026-09-19.md`** — five shot-distance bands, four columns each: today's flat box, Model A at t=1.0, Model A at t=0.7, and the ball's own distribution for comparison. Density maps, 40,000 draws per panel, each scaled to its own maximum so shape and spread are what to compare.

The deep band is the clearest statement of the problem:

| 40+ deep | mean x | mean distance from rim | y spread (sd) |
|---|---|---|---|
| **TODAY** | 88.5 | **2.7** | 3.2 |
| Model A t=1.0 | 74.0 | 17.0 | 8.4 |
| Model A t=0.7 | 76.5 | 14.5 | 6.0 |
| **BALL** | 74.1 | **16.9** | 8.4 |

On a 48-unit shot the ball comes to rest a mean **16.9 units** from the rim with an 8.4-unit y spread, and today every crasher is sent to a box **2.7 units** from the rim with a 3.2 spread. Model A at t=1.0 reproduces the ball's figures to a tenth — as it must, being the same distribution — while landing in different places draw by draw.

## What was built

| commit | what |
|---|---|
| `1b27fa95f` | Step 0 — both references re-cut at the default tree |
| `4559c3955` | Model A behind `GOB_CRASH_SHOT_AWARE`, **default OFF** |

- **`BackEnd/utils/crash_destination.py`** — the model. Keyword-only, and it receives **only** `shooter_x`, `shooter_y`, `rim_x` and `tightness`. It never sees `result`, `bounce_spot`, the make/miss flag or the calling frame.
- **`ShotManager._crash_coords`** — one dispatch helper, wired into the **four live branches** (MAKE, shooting-foul miss, fast-break miss, HCO miss). **Branch 3 (defensive foul on a miss) is left untouched** — it authored 0 destinations in 160 games and the brief says to leave it.
- **Draw-neutral by construction**: two `randint` calls per crasher either way, only the ranges change. (The per-game draw count is verified in Stage 2, with the flag on.)
- **Flag-off is byte-identical**: 5/5 seeds on both arms against the pre-edit tree.

### The principle, enforced structurally

`bounce_spot` is computed at `shot_manager.py:2465`, **85 lines before** the HCO authoring, and `result["ball_bounce_x"]` is already populated there. Two tests in `tests/test_crash_destination.py` make reading it a build failure rather than a code-review question:

1. **A signature guard** — fails if `crash_destination` grows a parameter outside the allowlist, or one whose name contains `bounce`, `result`, `made`, `miss`, `outcome`, `foul`, `frame`, `locals`, `rebounder`, `winner` or `game`. Parameters must stay keyword-only so nothing can be smuggled past by position.
2. **An AST scan of the module body** — fails if the code ever touches `ball_bounce`, `bounce_spot` or `result`. It walks the tree rather than grepping text, because the docstrings deliberately *name* the thing they forbid and a text search would flag its own warning.

**Both are poisoned.** The signature check is asserted against a deliberately bad signature (`bounce_spot` as a parameter), and the AST scan was confirmed to catch `result["ball_bounce_x"]` in a stub. **14 passed, 1 skipped** (the draw-count assertion only runs inside the equiv harness).

## Stop

Stage 1 ends here. **The flag was not flipped, no games were measured with it on, and no second re-cut was made.** Jamie picks a tightness from the pictures.

One thing worth deciding alongside the tightness, because it changes what Stage 2 should expect: the mismatch table above scores crashers on *distance to where the ball ended up*, and by that measure a tighter model always wins — in the limit, a model that put every crasher on the rim would score better still on short shots. That is a coverage-versus-accuracy trade, not a pure optimisation, and the number cannot settle it.

## Not covered

- **Not measured in a game.** Every number here is static sampling of the model. The live mismatch, draw count, §8.1 guard, OREB share and outcome table are Stage 2.
- `select_rebounder_by_score`, the `randint(1, 6)`, the selection order and `uses_shot_arc`: untouched. The reorder is a later step.
- Get-back and release destinations: untouched — they already use AG and an IQ read in `covert_release`.
- The zone work, the foul system, the crash-apply flags, `animator.py:1213`, R1, R2: untouched. No balance number changed.
- **Branch 3 remains dead and undiagnosed** — reported, not investigated.
- **Not settled:** whether shot *type* (`outside` / `attack` / `inside`) should modulate the distribution independently of distance. Model A keys on distance alone, which is what `_bounce_variance_for_shot_distance` already does for the ball; `shot_type` is in the allowlist for a future variant but is unused.
