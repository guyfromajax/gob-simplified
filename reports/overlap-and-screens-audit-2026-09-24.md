# Player overlap, screens, and screen stat tracking — audit

**The overlap is a scale mismatch first and a positioning problem second, and the scale
mismatch is the cheap half.** The shipped player marker is a disc whose radius is set by
height; at the median league height of 75" it is **5.25 grid units wide**, while *every*
distance in the defensive posture vocabulary — deny 2.0, on-ball tight 2.5, normal 3.5,
loose 4.5 — is **smaller than one sprite**. The engine is asking for separations the sprite
cannot draw, and its only existing guardrail, `zone_sink.MIN_SEPARATION = 2.0`, was derived
from the 5th percentile of what the engine already does rather than from anything on screen.

**It is broad and low-grade, not a few pathological spots.** 74.78% of steps have at least
one pair of players inside 3.0 grid units; 14.50% of steps have at least one *exactly
coincident* pair (same rounded cell); 10.68% of all 9.99M pairs sit inside one sprite
diameter. No single builder owns it — the largest, `build_skeleton_animation_steps`, is
56.9% of exact coincidences but it also stamps 52% of all steps.

**Screens today have no spatial representation, and Jamie's claim is confirmed with one
correction that matters.** At runtime a screen is an `action: "screen"` *label* on a
position — no coordinate, no target, no defender, and **no screen event at all** (the
`{"type":"screen","by":…,"for":…}` events in the playbook source never reach the executed
skeleton). The correction: the screener *is* given a named `location`, and in **105 of 116
cases (90.5%) it is the same named location as the player he is screening for**. Screens
are therefore not merely non-spatial — they are an active, systematic *source* of the
overlap Jamie is seeing.

**The current screen stats count the script, not the screen.** `SCR_A` is one count per
scripted `"screen"` label in the executed skeleton (116 per game across both teams).
`SCR_S` is those same labels re-counted when the possession's shot happened to go in — so
`SCR%` is the team's shooting percentage on screened possessions wearing the screener's
name. A play literally called **"Double Screen For SG" credits 0.20 screens per possession**,
the lowest of any play that screens at all, while "Pick & Roll (Lower Wing)" credits 2.35.

Nothing built. No constant changed. Nothing merged.

---

## Footing (Rule 6e)

| | |
|---|---|
| Worktree / branch | `gob-animation-reward` / `feature/animation-reward` |
| HEAD | `5b894da4d` — **develop merged first** (`0307ad358`, documentation only: READY markers + an R2 manifest row; no engine code) |
| **Reference** | **`equiv_v3_reference_1f4af0ede_loosesag_nogate.json` — re-confirmed 160/160 on fp AND draws after the merge**, all four cells |
| Worker | `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5 |
| Env | `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process, game id `0xE0000+(seed−8000)` |
| Overlap census | n=40 seeds 8000–8039, **both arms**, SD=1 → 80 games, 221,037 steps, **9,988,199 pairs**, 0 errors |
| Pair-detail / counterfactual | n=12 seeds 8000–8011, played, SD=1 → 32,695 steps, 327,404 placements, 1,477,217 pairs |
| Screen census | seeds 8000, played, SD=1 |
| **Probe RNG-neutrality** | every probe reproduced seed 8000 **fp `a1d150579771387a` AND draws `77689`** — the reference value. Each calls the original first and adds no draw. |

---

# PART A — the overlap

## A1. The cheapest explanation: sprite scale — **CONFIRMED**

### The grid → pixel mapping

| fact | source |
|---|---|
| Court is **100 × 50 grid units** | `FrontEnd/static/js/phaser/utils/gridToPixels.js:9-13` — `pixelX = (x/100)*width`, `pixelY = ((50-y)/50)*height` |
| Logical canvas **1229 × 768**, `Phaser.Scale.FIT` | `bootGame.js:2338-2347` |
| Court image is stretched to fill the whole canvas — **no inset** | `gameScene.js:3382-3385` — `.setOrigin(0).setDisplaySize(config.width, config.height)` |

`FIT` scales the whole canvas uniformly, so sprite-size-in-grid-units is **scale invariant** —
it does not change with the browser window.

> **px per grid unit: 1229/100 = 12.29 horizontally, 768/50 = 15.36 vertically.**
> The grid is anisotropic on screen: a player disc is an **ellipse** in grid space, wider than tall.

### The rendered player

The shipped marker is v2 — `markerConfig.js` has `USE_HEADSHOT_MARKER = true` and
`USE_MARKER_V2_FEATURES = true`. Its radius is height-linked
(`createHeadshotMarkerV2.js:9-12`):

```js
headRadiusForHeight(h) { return Math.max(25.5, Math.min(39, 30 + (h - 72) * 0.75)); }
```

| player | head radius | **body width (grid)** | body height (grid) |
|---|---|---|---|
| 5'6" (66") — floor | 25.5 px | **4.15** | 3.32 |
| **75" — league median** (`LEAGUE_MEDIAN_HEIGHT_IN`) | 32.25 px | **5.25** | 4.20 |
| 6'4" (76") — v1 baseline | 33 px | **5.37** | 4.30 |
| 7'0" (84") — ceiling | 39 px | **6.35** | 5.08 |

(The legacy fallback marker is a radius-24 circle = 3.9 grid units wide, `createPhaserPlayer.js:32`.
The vignette adds a soft halo out to `headR + 15` at 0.18 alpha; the solid body is `headR`.)

### The answer, plainly

**Yes — the engine is happy with separations the sprite cannot visually sustain.**

| the engine's distance vocabulary | value | vs one median sprite (5.25) |
|---|---|---|
| `POSTURE_DENY_DISTANCE` | 2.0 | **62% overlapped** |
| `ONBALL_POSTURE_DIST["tight"]` | 2.5 | **52% overlapped** |
| `ONBALL_POSTURE_DIST["normal"]` | 3.5 | **33% overlapped** |
| `ONBALL_POSTURE_DIST["loose"]` | 4.5 | **14% overlapped** |
| `zone_sink.MIN_SEPARATION` | 2.0 | **62% overlapped** |

**Every shipped posture distance is smaller than one sprite.** Even the loosest on-ball
cushion still overlaps. This is not a physics problem — the model has no distance in it that
would render as two separate bodies.

`zone_sink.MIN_SEPARATION`'s own comment is the confession:

> *"the 5th percentile of today's nearest-other-defender distance on zone turns
> (p5 = 1.41 home offense / 2.00 away, 235k placements). Choosing the p5 means the guardrail
> permits essentially everything the current geometry already does."*

The guardrail was calibrated against the engine's own habits, never against the renderer.

**The cheapest available fix is a minimum-separation constant matched to sprite size** —
and because the sprite is height-linked, the honest form is *per-pair*: `headR(a) + headR(b)`
in grid units (~4.2–6.4), not one global number. That is a constant and a clamp, not a
physics system, and it should be ruled in before anything else is designed. **But see A3 —
it cannot be applied naively.**

## A2. The overlap census (n=40, both arms, SD=1 — 9,988,199 pairs)

### Distribution of pairwise distance

| bucket | pairs | share | def-off | def-def | off-off |
|---|---|---|---|---|---|
| **exact** (same rounded cell) | 28,746 | 0.288% | 22.8% | 30.1% | **47.0%** |
| < 1 | 24,270 | 0.243% | 54.9% | 27.8% | 17.3% |
| 1–2 | 110,043 | 1.102% | 63.8% | 27.0% | 9.2% |
| 2–3 | 200,034 | 2.003% | 66.1% | 26.5% | 7.4% |
| 3–4.3 | 411,816 | 4.123% | 65.5% | 23.2% | 11.3% |
| 4.3–5.4 | 291,412 | 2.918% | 61.5% | 26.5% | 11.9% |
| ≥ 5.4 | 8,921,878 | 89.324% | 54.6% | 21.7% | 23.7% |

Cumulative: **3.64% of all pairs are under 3.0**, **7.76% under 4.3** (smallest sprite),
**10.68% under 5.4** (median-to-6'4" sprite).

Per pair type, share of that type inside one sprite:

| pair type | pairs | < 3.0 | < 4.3 | < 5.4 | exact |
|---|---|---|---|---|---|
| def-off | 5,541,685 | 4.01% | 8.88% | 12.12% | 0.118% |
| def-def | 2,210,370 | 4.44% | 8.76% | 12.26% | 0.392% |
| **off-off** | 2,236,144 | 1.91% | 3.99% | 5.55% | **0.605%** |

**Offence-on-offence is the least likely to be merely close and the most likely to be exactly
coincident** — 5× the def-off exact rate. That is the screen signature (Part B).

### How many players are involved per step

| players in a sub-3.0 overlap | steps | share |
|---|---|---|
| 0 | 55,753 | 25.22% |
| 2 | 75,909 | 34.34% |
| 3 | 15,704 | 7.10% |
| 4 | 40,231 | 18.20% |
| 5+ | 33,440 | 15.14% |

> **74.78% of steps have at least one sub-3.0 overlap. 14.50% have at least one exact
> coincidence.** 15% of steps have five or more players stacked.

### Which roles collide, and where

Exact coincidences, top pairs:

| pair type | roles | n |
|---|---|---|
| **off-off** | **O-C / O-PF** | **3,367** |
| def-def | D-PG / D-SG | 2,753 |
| def-off | D-PG / O-PG | 2,657 |
| off-off | O-PF / O-SF | 2,392 |
| off-off | O-C / O-SG | 2,128 |
| def-def | D-C / D-PF | 1,958 |

The single largest exact-coincidence pair in the game is **the two bigs standing in the same
cell** — which is precisely what the screen script asks for (Part B).

By region: **backcourt** leads (off-off 7,537 / def-off 5,766 / def-def 5,709), then
**paint** (off-off 5,556). Backcourt stacking is the reset/walk-up before a play starts;
paint stacking is help and rebounding converging.

### Attribution to the stamping builder

| builder | exact coincidences | share | steps it stamped |
|---|---|---|---|
| `skeleton_step_emitter.build_skeleton_animation_steps` | 21,835 | 56.9% | 115,226 |
| `dynamic_hct_step_emitter._build_loop_step` | 5,410 | 14.1% | 17,569 |
| `shot_micro_movements.build_shot_micro_steps` | 2,761 | 7.2% | 15,184 |
| `transition_bridge.build_walk_up_step` | 2,746 | 7.2% | 30,850 |
| `transition_bridge.build_pass_step` | 1,857 | 4.8% | 20,970 |
| `skeleton_step_emitter._scramble_leg` | 781 | 2.0% | **285** |

Normalised, the outlier is `_scramble_leg`: **781 coincidences from 285 steps — 2.7 per step.**
Everything else is roughly proportional to how many steps it stamps. So the problem is
**systemic, not localised** — with one genuinely pathological spot worth its own look.

### Answer

**A broad, low-grade problem.** Three quarters of steps contain at least one visually
unacceptable overlap, spread across every builder in rough proportion to its volume. It is
not a handful of bad sites; it is the whole placement vocabulary being calibrated below
sprite scale.

## A3. What a separation pass would collide with

### `zone_sink.MIN_SEPARATION = 2.0`

- **Where:** `zone_sink.py:325-328`, inside `_escape_if_rim_ward` only — the *zone sink escape*,
  Jamie's 2026-09-21 call letting a defender with nobody in his area stand outside his polygon.
- **What it protects:** only that the escape does not create a *tighter* overlap than the game
  already tolerates. It is checked against `others` (other defenders only), and only when the
  escape fires.
- **Global pass vs it:** a global pass **subsumes it entirely** — at any threshold ≥ 2.0 the
  local check can never bind first. It would not fight it. The constant should be retired into
  the global one rather than left as a second, weaker opinion.

### The naive counterfactual — a flat 3.0 minimum on all pairs

n=12 games, 327,404 placements, 1,477,217 pairs:

| | |
|---|---|
| **Placements it would move** | **82,899 of 327,404 = 25.32%** — one placement in four |
| Pairs it would separate | 53,796 — def-off 32,951, def-def 14,633, off-off 6,212 |
| Of those pairs, defender on **his own man** | **15,388 = 28.6%** |

Of the **def-off** pairs under 3.0, **46.7% are a defender sitting on the man he is
assigned to** — that is deny (2.0) and help working exactly as shipped. The other 53.3% are a
defender inside 3.0 of someone he is *not* guarding.

> **This is the number that decides the design.** A flat rule would move a quarter of all
> placements, and **28.6% of what it separates is deliberate defensive work** — deny, help
> sag, basket shade, sink. A pass that cannot tell "overlapping" from "both correctly doing
> their job in a crowded place" would undo a third of this month's shipped defensive shape.

Posture attribution of the defenders it would move: 43.1% off-ball `normal`, 6.0% on-ball
`normal`, and **51.0% untagged** — placed by something other than `_apply_defender_posture`
(fast break, tip-off, non-HCO paths). Any separation pass has to cover that half too; it
cannot live inside the posture code.

Top sub-3.0 role pairs are dominated by **same-position matchups** — D-C/O-C (4,414),
D-PG/O-PG (3,578), D-PF/O-PF (2,948) — i.e. mostly the defence doing its job, plus
D-C/D-PF (2,728) and D-PG/D-SG (2,527), which are the genuine defender-on-defender collisions.

### Blast radius

A 3.0 rule pushes each member of a colliding pair `(3−d)/2` — at most 1.5 grid units, and
under 0.5 for most pairs. Against the thresholds in play:

| threshold | value | exposure |
|---|---|---|
| `CONTEST_EUCLIDEAN_RADIUS` | 11 | a ≤1.5 push can cross it only for pairs already at 9.5–12.5; contest is measured defender→shooter, and **46.7% of the def-off pairs being moved are exactly that pair** |
| `STEP_IN_OPENNESS_MIN` / `_OPEN` | 5.0 / 10.0 | cushion-based; a 1.5 push is **30% of the 5.0 floor** — this is the most exposed consumer |
| `BACKDOOR_OPENNESS_MIN` / `_OPEN` | 3.0 / 8.0 | a push off a 2.9 cushion crosses the 3.0 "still covered" line directly |
| `BACKDOOR_LANDING_OPEN_RADIUS` | 8.0 | rim-help test; paint is the #2 collision region, so pushes there are common |
| drive corridor `HCO_CUTOFF_PATH_CORRIDOR` | 11.0 | wide relative to a 1.5 push; low exposure |

*(The "3.0 / 9.0 proximity bands" in the brief are analysis buckets from the AG-spread census,
not engine constants. The real band constants are the openness thresholds above.)*

**The exposure is real but bounded.** The dangerous ones are the openness floors at 3.0 and
5.0, where a 1.5-unit push is a large fraction of the band.

---

# PART B — what screens are today

## B4. The whole screen path

### `calculate_screen_score` — `BackEnd/utils/shared.py:1467`

```python
base = ST*0.5 + AG*0.2 + IQ*0.2 + CH*0.1
return base * random.randint(1, 6)
```

| | |
|---|---|
| **Callers** | **exactly one live caller**: `shot_manager.py:3214`. (`main.py:28` is an import only.) |
| **Inputs** | the screener's own `ST / AG / IQ / CH`. **No defender. No team attributes. No coordinates. No distance.** |
| **Randomness** | `random.randint(1, 6)` — the **global `random` module**, not `sim_rng` |
| **Output range** | 0–600 (attribute composite 0–100 × d6) |
| **Downstream use** | `shot_score += screen_score * 0.15` — one additive term in the shot roll, nothing else |

The screener **is** a specific `Player` object (`roles["screener"]`, guarded by
`if screener and screener != shooter`). So it is not a team-level abstraction — but the
player identity is used **only** to look up four attributes.

### Is there any spatial representation? — **No, at runtime**

| | |
|---|---|
| Coordinate on the screen score | none |
| Target (who is being screened) | not passed to the score at all |
| Defender considered | **none** |
| Screen **events** in the executed skeleton | **zero.** Runtime event types across a full game: `shot` 74, `d_foul` 8, `dead_ball_turnover` 7, `steal` 3, `o_foul` 2 |
| Screen **actions** in the executed skeleton | 116 per game, as `pos_actions[pos].action == "screen"` |

The playbook *source* does carry richer screen events —
`base_skeletons.py:77-78` has `{"type":"screen","by":"PG","for":"SG"}` and
`{"type":"screen","from":"PF","to":"C"}` (**two incompatible key schemas** for the same event
type). **Neither survives into the executed skeleton.** The only live artefact is the action label.

### The correction to "no spatial representation"

The screener **does** get a `location` — and it is the wrong one:

> **105 of 116 screen actions (90.5%) place the screener at the same named `location` as
> another offensive player** — the one he is screening for. `PG SCREEN "upper wing"` next to
> `SG DRIFT "upper wing"`; `PF SCREEN "upper lowPost"` next to `C DRIFT "upper lowPost"`.

Named spots are exact coordinates (`HCO_STRING_SPOTS`, e.g. `upper midCorner` = (81,43)), so
two players sent to one spot land in one cell. **This is the direct mechanical cause of the
O-C/O-PF exact coincidence being the single largest in the game (3,367).**

*(Method note: `pos_actions` carry **`location`**, not `spot`, at runtime — every consumer
reads `action_info.get("location") or action_info.get("spot")`. A first pass of this audit
read `spot`, found it uniformly `None`, and would have wrongly concluded the screener has no
location at all. The 90.5% figure is from `location`.)*

### Do off-ball players go anywhere to screen?

They are *sent somewhere* — to the receiver's own spot — but nothing checks a defender,
nothing contests, and nothing resolves. The playbook resolves the screen's **effect** in the
shot roll (`+0.15 × screen_score`) while the animation independently walks the screener onto
his teammate. **The two are not connected.**

### Frequency (seed 8000, played, SD=1 — both teams)

108 HCO resolutions, **116 screen actions = 1.07 per possession**:

| playcall | poss | screens | screens/poss | made% |
|---|---|---|---|---|
| Pick & Roll (Lower Wing) | 17 | 40 | **2.35** | 29.4% |
| 4-1 Flex Motion | 16 | 26 | 1.62 | 50.0% |
| Base Post Play | 19 | 29 | 1.53 | 5.3% |
| 5-0 Motion | 9 | 8 | 0.89 | 11.1% |
| 4-1 Motion | 16 | 9 | 0.56 | 25.0% |
| **Double Screen For SG** | 20 | 4 | **0.20** | 15.0% |
| 3-2 Motion | 8 | 0 | 0.00 | 50.0% |
| Outside / Attack | 3 | 0 | 0.00 | — |

**A play named "Double Screen For SG" produces the fewest screens of any screening play**, and
"3-2 Motion" produces none. Whatever `SCR_A` tracks, it is not the play's intent.

## B5. What the screener would need to target

| piece | exists? | where |
|---|---|---|
| Screen **receiver** identifiable at call time | **In the playbook source only** — `events[].for` / `.to`, and the top-level `"screener"` key (e.g. `COLORADO["screener"] = "PF"`). **Not in the executed skeleton.** Recovering it means either preserving the event or re-deriving it from the shared `location`. |
| **Matchup map** (receiver → his defender) | **Yes** — `BackEnd/utils/man_defense_matchups.py` |
| Its shape | `{def_pos: off_pos}`, **positions not player ids**; default position-on-position |
| Where it lives | `game_state["man_defense_matchups"]` (user) / `["man_defense_matchups_computer"]` (CPU) |
| Lifetime | **Reset to defaults at each break** (timeout, quarter break, foul out) — otherwise persists across possessions |

### Every consumer a switch would have to reach — **the key question**

`get_matchups_for_defending_team` is read at **18 sites across 5 engine modules**:

| module | sites | what it drives |
|---|---|---|
| `engine/defender_placement.py` | 1071–1073 | **where each defender stands** |
| `engine/step_state.py` | 32, 148 | the frozen per-step defender grid |
| `engine/attack_drive_clearance.py` | 14, 1073 | **drive help-cutoff** — who rotates on a blow-by |
| `engine/motion_read_map.py` | 17, 94 | offensive read/mismatch scoring (1:1 matchup edge) |
| `engine/phase_resolution.py` | 6584/6593, 7021/7032, 7201/7226, 7305/7349, 8005/8024 | shot contest, help, role resolution |

Add the **shot contest** path in `shot_manager.py`, which resolves the contesting defender
from the same role plumbing.

### Is it mutable mid-possession? — **No, and that is the finding**

Writes to the man matchup map are only:

| site | when |
|---|---|
| `man_defense_matchups.py:49-50` | `reset_matchups_to_defaults` — at breaks |
| `api.py:1899-1903`, `3967-3971` | hydration on game load |
| `api.py:6556` | the user's Defense Matchups popup |

**Nothing in the engine ever reassigns a man matchup mid-possession.** A switch has no
precedent in the man path.

**The precedent that does exist is in the zone path.** `shared_defense.py:1326-1356` builds
`defender_to_offensive_player` and `overlap_guarded_by` per turn, by detecting overlapping
zones and calling `_resolve_overlap_assignments`. Note what it does: it derives a **separate,
per-turn assignment map** rather than mutating the persistent one.

> **That is the shape a switch should follow** — a per-possession override layer that the 18
> consumers read *through*, rather than a write into `game_state`. Mutating the persistent map
> would leak a switch across possessions until the next break.

---

# PART C — what we are sunsetting

## C6. The current SCR_A / SCR_S tracking

### Where they are incremented

**Two sites; only one is live.**

| site | status |
|---|---|
| `phase_resolution.py:3810-3817`, inside `generate_logic()` | **DEAD.** `generate_logic` has no callers — `phase_resolution.py:8550` says `"✅ REMOVED: Old generate_logic() call"`. |
| `phase_resolution.py:record_hco_screen_stats()` (:8471), called from :8465, :9153, :9646 | **LIVE** |

The dead one is worth reading anyway, because it shows the intent that was abandoned:

```python
player.record_stat("SCR_A")
success = random.randint(1, 2)     # 50% chance
if success == 1:
    player.record_stat("SCR_S")
```

…a literal coin flip, inside a `try/except Exception: pass`, in a function whose return value
is a `PLACEHOLDER` `random.uniform(-1, 1)`.

The live one:

```python
if action != "screen": continue
player.record_stat("SCR_A")
if shot_made: player.record_stat("SCR_S")
```

### What they actually count, in plain language

- **SCR_A** — how many times the *script* labelled this position "screen" in the executed
  skeleton. One per label per step. Not one per screen: a single screen held across four
  steps counts four times.
- **SCR_S** — the same labels, re-counted when *the possession's shot went in*.

### Per-game values (seed 8000, both teams)

| | |
|---|---|
| `record_hco_screen_stats` calls | 108 |
| **SCR_A** | **116** |
| **SCR_S** | **25** |
| **SCR%** | **21.6%** |
| possessions ending MAKE at that call site | 28 of 108 = 25.9% |

### Why it is flawed — evidence, not agreement

1. **SCR_S has no causal link to the screen.** It is `shot_made`. A screener who sets a
   perfect screen on a missed shot scores 0; a screener standing still on a made heave scores 1.
   SCR% (21.6%) simply tracks the make rate of screened possessions (25.9%).
2. **It counts steps, not screens.** 116 attempts across 108 possessions from a scripted
   label held over multiple steps.
3. **It contradicts the playbook.** "Double Screen For SG" → 0.20 screens/poss; "3-2 Motion" → 0.
4. **It is blind to the defence.** No defender is consulted at any point — so no screen can
   ever fail on its own terms.
5. **It shares nothing with the shot math.** `calculate_screen_score` (which *does* use the
   screener's attributes) feeds the shot roll and never touches SCR_A/SCR_S. The stat and the
   effect are two unrelated systems, as the code comment at `shot_manager.py:3211` admits:
   *"Screener bonus (shot math only; SCR_A / SCR_S come from the executed skeleton)"*.
6. **A screener's own attributes do not affect his own stat at all.** ST/AG/IQ/CH change the
   shot bonus but not SCR_A or SCR_S.

### Everything that reads them

| consumer | file | breaks if the definition changes? |
|---|---|---|
| Box score (player rows + totals) | `FrontEnd/static/box-score.js:909, 929, 993-994, 1142-1143` | displays only — **no** |
| League stats table, `SCR%` column | `FrontEnd/static/stats.html:89, 131-133, 180, 201-216, 238` | displays only — **no** |
| Franchise command center | `franchise-command-center.js:2028-2029, 2973-2974, 3346, 3365-3366`; `.html:228` | displays only — **no** |
| Player detail page | `player-detail.js:295-296` | displays only — **no** |
| Team aggregation | `team_stats_aggregator.py:55, 128, 142` | zero-init + sum — **no** |
| Stat registry / schema | `constants/__init__.py:28`, `team_manager.py:1120-1121`, `main.py:1161` | key must survive — **no** |

> **Nothing feeds player development, attribute progression, awards, or CPU decisions.**
> I searched the development/EOG/progression paths specifically: SCR_A/SCR_S appear in
> **no** progression code. **This stat is display-only and safe to redefine.** That is the
> single most important fact for Phase 3 — the sunset is unusually cheap.

### Sibling stats with the same defect — **yes, one**

`DEF_A` / `DEF_S` share the schema and the ceremony. `DEF_A` is recorded at
`shot_manager.py:3190, 3199` for the primary and second defender on every contested shot.
It is a genuine *attempt* count — better grounded than SCR_A, which counts script labels —
but `DEF_S`/`DEF%` inherits the same shape of problem: success is defined by the shot result,
not by the defender's own contest quality. **`HELP_D` is worse: it is in the stat registry
(`constants/__init__.py:28`) but help defence was removed from the engine entirely**
(`shot_manager.py:3206`: *"Help defense removed"*; *"help_defender is always None now"*), so
it is a permanently-zero column still rendered in the box score.

---

# PART D — the shape of the work (described, not written)

## Phase 1 — the separation pass

| | |
|---|---|
| **Where** | A single pass over the step's **final stamped end coords**, immediately before `stamp_tween_durations` — the one place all ten players exist together and nothing downstream redraws them. |
| **Rule 26b** | The freeze makes this safe *and* mandatory: `GOB_PLACEMENT_FREEZE` is ON, so a step's defender row is write-once. A separation pass that runs **after** the freeze row is written must **write back through the freeze**, not beside it, or the frozen row and the rendered coord diverge — the same divergence class as the AG-spread tween mismatch. It must also `announce_blocked_write` when it corrects a frozen row: **a guard that corrects must announce.** |
| **Flag** | `GOB_BODY_SEPARATION`, default OFF |
| **Reference re-cut** | **Yes, eventually** — it moves ~25% of placements. Flag-OFF must be byte-identical (160/160). |
| **Deterministic or RNG?** | **Deterministic, and it should stay that way.** A pure rule (sort pairs by distance, push apart along the connecting axis, iterate to a fixed point) draws nothing and is clairvoyance-safe by construction. Introducing RNG here would put draws inside the animation layer, where the AG work has already shown they are hard to keep aligned. **If** a contest is wanted later, it needs the box-out shape — but not to start. |
| **Rule or contest?** | **Start with a rule, and not "defence holds, offence yields."** The data says the naive rule is wrong: 46.7% of sub-3.0 def-off pairs are a defender correctly on his man. The rule must be **assignment-aware**: never separate a defender from the man he is assigned to; separate def-def, off-off, and def-off-not-his-man. That alone addresses the def-def (27.2%) and off-off (11.6%) collisions — including the C/PF stack — without touching deny or help. |
| **What could go wrong** | (a) the openness floors at 3.0 and 5.0 — a 1.5-unit push is a large fraction of them, and `BACKDOOR_OPENNESS_MIN` 3.0 is crossed directly; (b) 51% of the defenders involved are placed outside `_apply_defender_posture`, so the pass cannot live in the posture code; (c) iterating to a fixed point in a crowded paint can oscillate or push a player out of bounds — it needs a court clamp and an iteration cap; (d) `zone_sink.MIN_SEPARATION` becomes dead and should be retired, not left as a second opinion. |
| **Estimate** | **Medium.** The pass itself is small; the freeze write-back, the assignment-awareness and the openness blast radius are what make it medium rather than small. |

## Phase 2 — spatial screens, muscle-through / switch

| | |
|---|---|
| **Where** | Screener placement in the skeleton emit path (the `location` resolution that currently sends him to the receiver's spot), plus a new per-possession matchup override layer. |
| **Flag** | `GOB_SPATIAL_SCREENS`, default OFF |
| **Reference re-cut** | **Yes** — it changes placement and, via the switch, contest and help. |
| **Steps** | (1) preserve the screen event's `by`/`for` into the executed skeleton — and **unify the two key schemas** (`by`/`for` vs `from`/`to`) first; (2) resolve the receiver's defender through the matchup map; (3) target the screener at **that defender's** body instead of the receiver's spot; (4) resolve muscle-through vs switch. |
| **The switch** | Must be an **override layer read by all 18 consumer sites**, following the zone precedent (`defender_to_offensive_player`), **not** a write into `game_state["man_defense_matchups"]` — that map survives until the next break and a leaked switch would silently persist across possessions. |
| **What could go wrong** | The 18 consumers are the risk, and they are not uniform: `defender_placement` and `step_state` need the switch *before* placement; `attack_drive_clearance`, `motion_read_map` and the shot contest need it *after*. Missing one leaves a defender guarding a man he switched off. A switch also changes who contests the shot, which moves scoring — expect outcome movement here, unlike Phase 1. |
| **Estimate** | **Large.** |

## Phase 3 — SCR_A / SCR_S rebuilt, old tracking deleted

| | |
|---|---|
| **Where** | New increments at the Phase 2 screen resolution; delete `record_hco_screen_stats` and the dead `generate_logic` block. |
| **Flag** | None needed beyond Phase 2's — the stat follows the model. |
| **Reference re-cut** | **No.** Stats are not in the fingerprint, and the new increments draw nothing. |
| **Definition** | SCR_A = one per *resolved screen*, once per screen not once per step. SCR_S = the screen achieved its effect (defender impeded / switch forced), decided at resolution — **never the shot result**. |
| **What could go wrong** | Very little, and this is the phase to be confident about: **every consumer is display-only** and nothing feeds development or awards. The only care needed is that the keys survive in the registry (`constants/__init__.py:28`, `team_manager.py:1120-1121`) so the aggregator and box score keep rendering, and that historical rows are understood to be on the old definition. |
| **Also worth doing here** | `HELP_D` is a permanently-zero column for a system that no longer exists — delete or hide it. |
| **Estimate** | **Small.** |

## Which phase first?

**Phase 1, and question A1 does not change that — it sharpens it.**

The scale mismatch means Phase 1's job is smaller than it first appears: it is a constant
matched to sprite size plus an assignment-aware clamp, not a physics system. It is the only
phase that is deterministic, display-correcting, and independent of the other two. It fixes
the thing Jamie can actually see.

Two caveats worth stating plainly:

1. **Phase 1 will not fix the biggest single overlap.** The largest exact-coincidence pair
   (O-C/O-PF, 3,367) is *created* by the screen script sending two offensive players to one
   named spot. A separation pass would push them apart cosmetically while the script keeps
   aiming them at the same cell. **Phase 2 removes the cause; Phase 1 only hides it.** If
   Jamie wants the C/PF stack genuinely gone rather than nudged, the screener's `location`
   resolution is a small, targeted change that could be pulled forward out of Phase 2 — point
   the screener at the receiver's *defender* rather than the receiver — without the switch.
2. **A sprite-matched separation constant is not free.** At ~5.25 units it is larger than
   every posture distance the defence uses, so enforcing it globally would visibly loosen the
   defence. The honest first step is to separate only pairs that are **not** an assigned
   matchup, and to leave deny and help at their shipped distances even though they overlap on
   screen — i.e. accept that a defender guarding his man *should* look like contact.

---

## What I did not do

Built nothing, changed no constant, merged nothing. The only commits are this report and the
develop merge required before measuring.
