# Man loose / man deny in the equiv-v3 fixture, and complaint #3

**Loose and Deny are fully reachable in real play today** — a user cycles the in-game
Playcall Center defense card to "Loose Man" or "Deny Man", or sets a Man Defense % on the
playbook screen, and every CPU team on a franchise schedule already carries a 1–50% Deny
and Loose weight, so CPU teams call them on roughly two man possessions in three; only the
*fixture* never saw them, because fixture teams are built with an empty `playbook_settings`.

**At normal the off-ball help defender is not too close to his man** — he sits 7.77 off him
(weak side 10.36) and 14.58 from the rim — and Loose does not help, because it moves him a
further 3.8 *toward the ball* while leaving his distance to the rim unchanged (14.58 → 14.24).

**That is not one constant, it is a missing piece.** `HELP_SAG` only moves him along the
man→ball axis, and the only rim-ward term, `HELP_BASKET_SHADE`, is a flat 0.20 that reads
neither posture nor ball side. Doubling it flat drags the strong-side defender 3.6 off the
rim as well; scaling it by weak-sideness — the rule the shipped zone help shade already
uses — moves the weak side 13.20 → 10.52 and leaves the strong side alone.

---

## 1. Where posture comes from

| step | code | what it does |
|---|---|---|
| user / CPU sets a % | `playbook_settings["man_defense"]` = `{man_normal, man_tight, man_loose}` | the only input |
| CPU expands bare "man" | [turn_manager.py:3407-3424](BackEnd/models/turn_manager.py#L3407-L3424) `_select_man_defense_with_playbook_weights` | weighted random over those %; **falls back to `man` when all are 0 or absent** |
| becomes the playcall | `defense_playcall` = `man` / `man-tight` / `man-loose` | distinct catalog id, posture survives |
| becomes a posture | [phase_resolution.py:5070-5091](BackEnd/engine/phase_resolution.py#L5070-L5091) `_roll_defense_posture` → [defense_identity.py:52-67](BackEnd/utils/defense_identity.py#L52-L67) | keyword match: deny/pressure/tight → `tight`, loose/sag → `loose`, else `normal` |
| becomes a position | [shared_defense.py:2048-2087](BackEnd/utils/shared_defense.py#L2048-L2087) `_apply_defender_posture` | on-ball cushion, off-ball deny, off-ball help |

**What a real user has to set** — either is enough, both are wired end to end:

- **In-game, fastest:** Playcall Center → the **Defense card** → arrows cycle
  `Base Man / Deny Man / Loose Man / 2-3 Zone / 3-2 Zone / 1-3-1 Zone`, click to select
  ([court.html:6059](FrontEnd/static/court.html#L6059), mapped to `man_tight` / `man_loose`
  at [court.html:6161-6168](FrontEnd/static/court.html#L6161-L6168)). The override persists
  until the red X clears it.
- **Persistent:** Playbook screen → Defense → **Man Defense** → set a % on *Deny Man* or
  *Loose Man*. All three rows ship `is_active: True`
  ([gameplan_routes.py:2954-2968](BackEnd/api/gameplan_routes.py#L2954-L2968)).

**Does the CPU ever choose loose or deny in a normal league game? Yes — in franchise, almost
always.** [cpu_playbook_customization.py:402-404](BackEnd/utils/cpu_playbook_customization.py#L402-L404)
assigns CPU man weights with `_random_capped_three(..., max_pct=50)`, which gives **all
three keys at least 1% and at most 50%** ([:223-228](BackEnd/utils/cpu_playbook_customization.py#L223-L228)).
So every customized CPU team mixes Base / Deny / Loose, and Base is a minority of its own
man calls. This runs for the CPU teams on the user's franchise schedule from week 1
([api.py:262-336](BackEnd/api/api.py#L262-L336)); it does **not** run in single / exhibition
games, and it never touches the user's own team.

**The user's own default is 100% Base.** [gameplan_routes.py:823-826](BackEnd/api/gameplan_routes.py#L823-L826)
initialises `man_normal 100 / man_tight 0 / man_loose 0`, under the comment *"Man defense:
only normal is active for now."* That comment is stale — all three are live — but the
default it writes is why a user who never opens the playbook only ever *plays* Base Man.

**Why the fixture never saw them:** `TeamManager` builds every team with
`self.playbook_settings = {}` ([team_manager.py:445](BackEnd/models/team_manager.py#L445)),
so the picker finds no man % and returns `man` every time. Nothing in the engine was
blocking loose or deny.

### Tagged separately: the legacy `get_spacing` non-BH fallback is dead code

[shared_defense.py:2003-2007](BackEnd/utils/shared_defense.py#L2003-L2007) — the
`get_spacing(aggression_level, is_ball_handler=False)` 1/2/3-unit branch — is the `else` of
the `ball_spot_used` chain, and **no production caller can reach it**:

| caller | `ball_spot` passed | `ball_spot_used` | branch taken |
|---|---|---|---|
| `get_defender_coords` ([:2177](BackEnd/utils/shared_defense.py#L2177)) | none — six positional args, the parameter is dropped | `"key"` | first branch ([:1860](BackEnd/utils/shared_defense.py#L1860)) |
| `rim_runner_fast_break` ([:205](BackEnd/engine/rim_runner_fast_break.py#L205), [:215](BackEnd/engine/rim_runner_fast_break.py#L215)) | `bh_spot`, always `"lower wing"` or `"upper wing"` ([:164](BackEnd/engine/rim_runner_fast_break.py#L164)) | those two | the wing branches ([:1876](BackEnd/utils/shared_defense.py#L1876), [:1920](BackEnd/utils/shared_defense.py#L1920)) |

There is no third production caller. Separately: on the HCO path the whole non-BH legacy
geometry is **computed and thrown away** — `_apply_defender_posture` recomputes the position
from man/ball/basket and only returns the legacy `def_coords` for inside-man matchups
(27.0–27.9% of off-ball calls). Both are dead weight, not defects; neither is in scope here.

---

## 2. The fixture option — additive, no engine change

`EQUIV_MAN_POSTURE=normal|loose|deny` (unset = today) sets 100% on the matching
`man_defense` row of **both** teams' `playbook_settings`, the same dict a saved user playbook
and a CPU-customized playbook write. It is applied in the worker beside the existing
`strategy_settings` assignment. `shared_defense.py` is untouched. Commit `de8cf1c92`.

**The reference does not move.** With the option unset and the census on,
`equiv_v3_reference_32db56c77_helpshade` reproduces on **fp AND draws**:

| cell | sim | played |
|---|---|---|
| `SEED_DEFENSES=1` | 40/40 | 40/40 |
| `SEED_DEFENSES=0` | 40/40 | 40/40 |

**160/160.** Re-confirmed 40/40 (SD=1, sim) after the census gained its final fields. No re-cut.

**The option produces the posture** (sim arm, n=40, SD=1):

| setting | off-ball posture calls | HCO possessions by posture | man playcall |
|---|---|---|---|
| unset | normal 192,148 | normal 4,675 / None 153 | `man` 50% |
| `normal` | normal 195,673 | normal 4,650 / None 148 | `man` 50% |
| `loose` | **loose 190,421** / normal 100 | normal 2,360 / **loose 2,377** / None 148 | `man-loose` 50% |
| `deny` | **tight 194,569** / normal 112 | normal 2,325 / **tight 2,286** / None 155 | `man-tight` 50% |

The residual "normal" at loose/deny is the zone half of the slider-2 defense mix (zone
possessions carry no man posture); the ~100 stray off-ball normal calls are non-HCO turns.

---

## 3. Complaint #3, measured (sim arm, n=40, seeds 8000-8039, SD=1)

Off-ball man placements only. Played arm agrees to ±0.1 on every number below.

| | normal | loose | deny |
|---|---|---|---|
| gap to man — mean / p50 / p90 | 7.77 / 7.10 / 12.00 | 11.56 / 10.20 / 19.00 | **2.09 / 2.20 / 2.20** |
| distance to ball | 14.85 / 14.00 / 21.60 | 11.25 / 10.60 / 16.80 | 18.49 / 16.30 / 29.50 |
| distance to rim | 14.58 / 14.90 / 19.30 | **14.24** / 14.10 / 19.90 | 19.81 / 20.80 / 25.60 |
| sag along man→ball axis | 6.48 | 10.45 | 2.10 |
| sag along man→rim axis | 6.57 | 8.74 | 0.77 |
| `HELP_ANCHOR_FLOOR` binds | x 16.3% / y 11.0% / **either 27.3%** / both 0.0% | x 16.1% / y 10.6% / either 26.6% / both 0.0% | n/a |
| in the passing lane | — | — | **99.7%** |
| inside-man lock (posture ignored) | 27.0% | 27.9% | 27.3% |

By ball side, on the zone help shade's own ramp (`zone_sink.SIDE_SPAN` + `ball_centrality`;
"strong" includes a central ball, where the zone rule says there is no weak side):

| | share | gap to man (normal) | defender→rim (normal) | man→rim | gap to man (loose) | defender→rim (loose) |
|---|---|---|---|---|---|---|
| strong | 54.2% | 6.29 | 15.24 | 19.79 | 9.10 | 15.16 |
| middle | 17.2% | 8.12 | 14.71 | 21.73 | 11.69 | 12.99 |
| weak | 28.6% | **10.36** | **13.25** | 21.21 | **16.07** | **13.28** |

**Deny is correct and needs nothing.** 2.09 off the man (`POSTURE_DENY_DISTANCE` 2.0, grid-
rounded), 99.7% of the time genuinely between his man and the ball. One caveat for the eye:
p50 and p90 are *both* 2.20 — deny carries no jitter at all, so all four off-ball defenders
sit at an identical distance. That reads mechanical; it is a tuning note, not a defect.

**Normal is not "too close to his man."** 7.77 mean, weak side 10.36, and at 13.25 from the
rim the weak-side helper is already inside the free-throw line. On a 100×50 grid over a
94×50 ft court that is ≈1 unit per foot (basketSpot 4.0 from the rim, low post 7.8, key 27.0).

**The real defect is what Loose buys.** Going normal → loose:

- gap to man **+3.79** (7.77 → 11.56), weak side **+5.71** (10.36 → 16.07)
- distance to rim **−0.34** (14.58 → 14.24), weak side **+0.03** (13.25 → 13.28)

Loose moves him *sideways toward the ball* and not one step toward the basket. He ends up
neither denying his man nor protecting the rim — floating. The loose picture shows it
plainly: four defenders strung along the near edge of the lane, ball-side of their men, with
the basket behind them unguarded.

### Is it a constant or a missing piece?

Priced from the stored samples (seeds 8000-8009, 33,790 placements; pure arithmetic on
man/ball/rim, `HELP_SAG_JITTER` pinned to 0 in every variant including the baseline, so
nothing is de-phased — a counterfactual, not a measurement of a built thing):

| posture=normal | defender→rim: strong / middle / weak | gap to man: strong / middle / weak |
|---|---|---|
| shipped (`HELP_BASKET_SHADE` 0.20 flat) | 15.25 / 14.71 / 13.20 | 6.29 / 8.06 / 10.33 |
| flat bump to 0.40 everywhere | 11.65 / 10.55 / **10.25** | **9.56** / 12.21 / 13.90 |
| scaled: 0.20 × (1 + weakness) | 14.86 / 12.64 / **10.52** | 6.69 / 10.11 / 13.57 |

**One constant cannot do it.** The flat bump reaches the weak-side target (13.20 → 10.25)
but takes the strong-side defender with it (15.25 → 11.65, gap 6.29 → 9.56) — a one-pass-away
defender abandoning his man. The weak-scaled form reaches the same weak-side number
(13.20 → 10.52) and leaves the strong side essentially untouched (15.25 → 14.86).

**The magnitude is fine; the shape is wrong.** Man help has no read of ball side. The one
rim-ward term is flat, and the one thing posture *does* move is the ball axis. The zone side
already has the missing piece — `_apply_zone_help_shade` scales `HELP_BASKET_SHADE` by
weak-sideness using `zone_sink.SIDE_SPAN` and `ball_centrality`. Man should get the same
read. That is a build, not a tune, and it is not in this brief's scope.

---

## 4. Outcomes, seed-paired (played arm, n=120, seeds 8000-8119, SD=1)

CI = 1.96 × SEM of the **per-seed difference**.

| metric | normal | loose | deny | loose − normal | deny − normal |
|---|---|---|---|---|---|
| points / team | 73.57 ±1.79 | 75.63 ±1.89 | 72.17 ±1.65 | +2.06 ±2.11 | −1.40 ±1.94 |
| possessions | 40.91 ±1.10 | 39.61 ±1.11 | 40.81 ±0.98 | −1.30 ±1.35 | −0.10 ±1.28 |
| FG% | 40.29 ±1.14 | 40.79 ±1.18 | 40.00 ±1.07 | +0.50 ±1.36 | −0.29 ±1.30 |
| 3PA share | 35.36 ±0.90 | 36.10 ±0.95 | 34.34 ±0.81 | +0.74 ±1.15 | −1.02 ±1.11 |
| paint share | 29.05 ±0.87 | 28.91 ±0.86 | 31.27 ±0.93 | −0.14 ±1.12 | **+2.21 ±1.27** |
| steals | 17.47 ±0.66 | 17.64 ±0.78 | 16.86 ±0.79 | +0.17 ±1.01 | −0.61 ±0.96 |
| deflections | 8.96 ±0.50 | 9.21 ±0.54 | 9.46 ±0.57 | +0.25 ±0.73 | +0.50 ±0.73 |
| blocks | 10.14 ±0.54 | 9.47 ±0.57 | 10.69 ±0.59 | −0.68 ±0.73 | +0.55 ±0.81 |
| fouls | 31.13 ±1.07 | 32.92 ±1.07 | 31.74 ±1.06 | **+1.79 ±1.45** | +0.61 ±1.29 |
| freeze-miss | 2.43 ±0.29 | 1.93 ±0.24 | 2.28 ±0.28 | **−0.50 ±0.39** | −0.15 ±0.41 |

Only three differences clear their own CI, and each makes sense: **deny gives up the paint**
(+2.21 share — the whole team is out on the perimeter), **loose fouls more** (+1.79, more
closing distance to cover), and freeze-miss drifts down at loose. Points, FG%, 3PA share,
steals and blocks are all flat.

Read plainly: **posture is nearly free to play with today.** It changes what the court looks
like a great deal and what the scoreboard says almost not at all. Good for an eye test; also
a sign that the defensive read is not yet doing real work.

---

## 5. Pictures

- [reports/offball-man-normal-2026-09-22.png](reports/offball-man-normal-2026-09-22.png)
- [reports/offball-man-loose-2026-09-22.png](reports/offball-man-loose-2026-09-22.png)
- [reports/offball-man-deny-2026-09-22.png](reports/offball-man-deny-2026-09-22.png)

Four panels each: the off-ball men of one placement pass, each with his defender, the gap
drawn and numbered, the ball, the rim and the lane. Panels are the passes whose mean gap is
closest to that posture's **pooled median**, one per seed, so they are typical rather than
extreme. Away-offense passes are mirrored so every panel attacks the same basket. No 3pt arc
is drawn — the sim's three boundary is a per-spot x, not a circle.

---

## 6. Eye-test it in staging

1. Start any game as the defending team.
2. In the **Playcall Center**, find the **Defense card** (it reads "Man Normal" by default).
3. Use the up/down arrows to reach **Loose Man** or **Deny Man**, then click the card.
4. It stays set every possession until you clear it with the red **X**.

For a whole-season version instead: **Playbook → Defense → Man Defense** → put 100% on
*Loose Man* or *Deny Man*. To watch the CPU do it, play a **franchise** game — the CPU teams
on your schedule already carry Deny and Loose weights, so they mix all three without you
touching anything.

---

## Tunable Constants

Reported, not changed — these are Jamie's single tuning pass at the end.
All in [shared_defense.py:2024-2038](BackEnd/utils/shared_defense.py#L2024-L2038).

| constant | value | effect | what this measurement says |
|---|---|---|---|
| `ONBALL_POSTURE_DIST` | tight 2.5 / normal 3.5 / loose 4.5 | on-ball cushion off the BH toward the rim | not measured here (off-ball brief) |
| `POSTURE_DENY_DISTANCE` | 2.0 | off-ball deny: grid off the man, ball-side | delivers 2.09 and 99.7% lane occupancy — correct; carries no jitter, so all deny gaps are identical |
| `HELP_SAG` | normal 0.30 / loose 0.55 | fraction of the way from man toward **ball** | the only thing posture moves; raising it does not bring the helper toward the rim |
| `HELP_SAG_JITTER` | 0.10 | ±0–10% human jitter on the sag | pinned to 0 in the counterfactual so the variants are not de-phased |
| `HELP_BASKET_SHADE` | 0.20 | fraction of man→basket, added to the help spot | **the only rim-ward term, and it is flat** — reads neither posture nor ball side; this is the gap |
| `HELP_ANCHOR_FLOOR` | 0.30 | min follow in the man's basket-aligned axis | binds in one axis on 27.3% of off-ball calls, never in both |
| `_POSTURE_INSIDE_SPOTS` | 6 spots | inside men get base post-D, posture ignored | 27.0–27.9% of off-ball calls |
| `zone_sink.SIDE_SPAN` | 30.0 | the strong/weak ramp the zone shade uses | reused here only as a yardstick; man does not read it |

---

## Footing

equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 /
traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed-8000)`. **`SEED_DEFENSES=1` throughout for the measurements** (production
footing: the six real defenses are seeded, so zone calls play as zone); the reference
reproduction covers `SEED_DEFENSES` 1 and 0, sim and played. Geometry n=40 (seeds
8000-8039), both arms. Outcomes n=120 (seeds 8000-8119), played arm. CI = 1.96 × SEM.
sim arm = `_is_full_simulation` True throughout; played arm = False only inside the four
gated Animator methods at Pattern A.

The census wraps `_apply_defender_posture`, calls the original first, and only reads its
inputs and its return value — it draws nothing. That is proved rather than asserted: every
reference-reproduction run above had the census **on**.

Suite: `tests/` 3175 passed, 20 skipped, 112 xfailed, **0 failed, 0 XPASS**. The three
failures in `BackEnd/tests/` (`test_pre_training_decay_ranges_match_doc`, two in
`test_team_builder_court_persist.py`) are pre-existing — verified identical at `3b6d6dae3`
in a clean worktree, and nothing in the suite imports the files this brief touched.

Not merged.
