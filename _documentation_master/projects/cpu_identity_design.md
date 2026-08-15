# CPU Identity — DESIGN

**The design doc for CPU team identity.** For what is actually LIVE, read
[`06_Gameplay_Systems/CPU_Team_Identity_System.md`](../06_Gameplay_Systems/CPU_Team_Identity_System.md)
first — its ▶ SURFACE STATUS table is authoritative and this document is not.

**Last revised 2026-08-15.** Parts A (training) and B (unbuilt surfaces) below.

> **Merged 2026-08-15 from `cpu_team_identity_spec.md`**, which was ~60% superseded: its model,
> signals, fit function and slider sections describe shipped behaviour now documented in the
> system doc; its §6 training design was replaced wholesale by Part A here; its §7 substitution
> proposal was measured and rejected. What survived — the genuinely unbuilt surface designs —
> is Part B. The originals of the superseded sections are in git history
> (`cpu_team_identity_spec.md`, last content at `a6d909095`).

---

---

# PART A — TRAINING

Steps 1-3 SHIPPED. See §7 for the build log.

## A1. The defect this fixes

CPU auto-train does **not** train the way a user does. `franchise_routes.py` groups the roster
by development position and calls `execute_training` **once per position group**, each with its
own allocation:

```python
for pos, group in groups.items():
    allocations = _cpu_reference_allocation(pos)   # a DIFFERENT plan per position
    execute_training(group, ..., allocations, ...)
```

| | User team | CPU team (today) |
|---|---|---|
| Plans per week | 1 | up to 5 |
| Points per player | 24 (30 at camp) | ~17 |
| Position fit | every player eats a compromise | every player trains his ideal |

The user assigns one plan across a 12–15 man roster, so most players train attributes their
position discounts. CPU players each receive the plan fitted to their exact position. **CPU
spends fewer points but wastes none** — an advantage no human can replicate, and the inverse of
the intended "the user's edge comes from out-coaching the reference."

**Fix: one team-wide 24/30-point plan per CPU team per week, chosen by its identity.**

### What breaks when this lands

* **`_CPU_REFERENCE_BASE_BY_POS` loses its meaning.** Those numbers are *fitted* so
  `base × 1.65 focus amp` scores ~1.0 **per position** against the frozen
  `reference_allocation` anchor. One team-wide plan cannot hit 1.0 at every position.
* **`tests/test_cpu_reference_training.py` fails by design.** It locks those bases.
* **CPU player development changes league-wide** — players start eating fit discounts, so the
  uniform ~+38.7 RT arc shifts and diverges by position. **Requires a re-measured baseline.**

**It does NOT affect the offseason RT ladder.** `_coaching_accumulator_for_player` is
`return None` unconditionally, and its docstring states CPU teams record no allocation even
after the capture seam lands. CPU never feeds `season_coaching_quality`, so `coaching_f` stays
1.0 for CPU players regardless of what they train.

---

## A2. Weekly coaching focus — RANDOM for now

✅ **SHIPPED `d3efecd1b`.** Each CPU team gets **one of 16** leaves per week.

**DERIVED from a hash of (franchise, team, season, week) — NOT drawn from an RNG.** The first
draft said `training_rng`, which was wrong: CPU teams train inside a ProcessPool and each
spawned worker builds its own `training_rng` from OS entropy, so a draw would make a team's
focus depend on WHICH WORKER claimed it, and re-running a week could hand it a different focus.
sha256, not `hash()` — the builtin is only stable while `PYTHONHASHSEED` is pinned.

| Family | Sub-options |
|---|---|
| `authoritarian` | discipline, rebounding, teamwork, execution |
| `systems-coach` | offense, defense, fast-breaks, press-trap |
| `player-maximizer` | top-3, attributes-4-6, custom, positional-focus |
| `culture-builder` | inspire, community, teamwork, confidence |

`execute_training` takes a single self-describing string (`"systems-coach-offense"` →
archetype + sub-option via `parse_coaching_focus`), so no extra plumbing is needed.

**Excluded: `player-maximizer-choose-attributes`.** It appears in
`COACHING_FOCUS_LEAF_DISPLAY_NAME` but is not handled in `_should_amplify_player_attr`, so it
would be a silent no-op. 16 real leaves, not 17.

**`player-maximizer-custom` needs `coaching_focus_custom_by_player`** — keep
`_cpu_reference_custom_focus` to supply it on the weeks that leaf is drawn.

> **Deliberately dumb for now.** Strategy in focus selection — and a per-team *coach identity*
> with a major and a minor (a discipline-major/systems-minor team is a Bobby Knight) — is
> planned, not scoped here. Focus choice is arbitrary so the ALLOCATION logic below can be
> measured without a second moving part.
>
> **Measured cost of giving up the always-optimal leaf: −0.14 ± 0.14 per player per week over
> 60 teams / 720 players — not distinguishable from zero.** I predicted a meaningful drop; there
> isn't one. (An earlier 24-team run read +0.22 and was noise.)

---

## A3. Allocation — 12 floors + 6 offensive + 6 defensive = 24

### A3.1 Why floors exist (this is the load-bearing constraint)

`PLAYER_ATTR_GAIN_RANGE_BY_POINTS` is not linear:

| points | range | E |
|---:|---|---:|
| **0** | **(−2, −1)** | **−1.5** |
| 1 | (1, 3) | +2.0 |
| 2 | (2, 3) | +2.5 |
| 3 | (2, 4) | +3.0 |
| 4 | (3, 5) | +4.0 |
| 5 | (3, 6) | +4.5 |

**0 → 1 is worth +3.5. The entire 1 → 5 span is worth +2.5.** A zero is −1 to −2 *every week,
guaranteed*, with no probability gate — about −26 to −52 over a season.

So spreading beats concentrating, and a 4 or 5 almost never repays what it costs elsewhere.
**4s should be ultra-rare; 2s and 3s carry identity perfectly well.**

**12 slots must never be 0** — the 9 `player_drills`, plus `conditioning` (ND), `free_throws`
(FT) and `film_study` (IQ), which train player attributes through the same table. Only `breaks`
and the 7 `team_drills` may be zeroed; those run the *team*-attribute path, where neglect decay
is probability-gated (25%, 10% for chemistry) and deliberately mild.

Because the 12 floors never drop below 1, **no legal plan ever zeroes a penalised slot** — so
the "don't zero the same thing two weeks running" rule can never fire, and the allocator needs
no cross-week state.

### A3.2 Base

All 12 never-zero slots start at **1** (= 12 pts). `breaks` and the 7 team drills start at **0**.

### A3.3 Why the first draft's `+2 / +1` pattern was wrong

**One plan covers the whole roster, so what matters is a attribute's AVERAGE fit across the
five positions — not its fit for the player it suits.** Every skill attribute is strong for two
positions and weak for three, so they all land in a narrow band:

| attribute | avg fit | points needed to HOLD roster-wide (JR/SR) |
|---|--:|---|
| **ND, IQ, FT** | **1.00** | **1** |
| SC, RB | 0.60 | 2 |
| SH, OD, ST, AG, ID, PS, BH | 0.52–0.59 | **3** |

`BH` is 1.00 for a PG and 0.25 for a PF/C; `ID` is 1.00 for a C and 0.25 for a PG. The averages
collapse to ~0.55 for all nine.

**So a skill emphasis must be 3 points or it is not an emphasis.** The draft's `+1` slot landed
on 2 points — below break-even for every skill attribute — meaning **seven of ten visions had a
secondary emphasis that still declined**, and Contain and Multiple had none that held at all.
A point spent to slow a decline reads as identity in the table and does nothing on the roster.

**Bucket 3 is ~3x more point-efficient than Bucket 2**, because ND/IQ/FT are fit 1.00 for
everyone. That is arithmetic, not preference, and it is what the two modes below exploit.

### A3.4 TWO MODES — the roster/skill split

Neither lever alone is right: skill emphasis is characterful but only reaches the two positions
that fit it; Bucket 3 reaches everyone but says little about identity. So a CPU team alternates,
and the split becomes the single dial future logic turns.

**FOCUS WEEK — sharp, reaches the players who fit the vision**

* 12 floors at 1
* **ONE** skill attribute at **3 points** (never 2 — see §A3.3)
* **ND and IQ lifted to 2** with the points a second emphasis would have cost
* the vision's team installs

> **Why one skill, not two — MEASURED live, weeks 5-6.** Focus weeks ran **−0.42**/player
> against roster weeks' **−0.06**, a real **−0.36** gap (n = 1,536 vs 1,512, |t| = 3.6). The
> cause is fit, not the emphasis idea: two skills at 3 buy **+0.32** of value over the floors,
> while the same 4 points as *one* skill at 3 **plus ND/IQ at 2** buy **+0.44** — ND/IQ are fit
> 1.00 for every position, skills average 0.56.
>
> Same budget, **~+0.12/player/focus-week by arithmetic, +0.26 ± 0.14 by dry run**, and the
> team keeps one sharp, legible emphasis. Camp is exempt — it skips decay and runs at 0.70, so
> every allocation gains there.

**ROSTER WEEK — reaches everyone**

* 12 floors at 1
* a **rotating +1 lift across the NINE SKILLS ONLY** — `ND`/`IQ`/`FT` excluded, starting
  point derived per (team, week)
* the vision's team installs

> **REVISED 2026-08-14 after a measured season.** The lift used to be fixed on ND/IQ/FT — the
> point-efficient choice, since those three are fit 1.00 for every position. It worked exactly
> as designed, which was the problem. Over 26 weeks (1,523 players):
>
> | | cumulative | % of players up |
> |---|--:|--:|
> | ND / IQ / FT | +15.3 / +14.0 / +8.7 | **100 / 100 / 99%** |
> | the nine skills | −1.3 to −2.8 | **30–40%** |
>
> Roster weeks gave every skill exactly **1 point — the bare floor** — while the three
> universals sat at **2.67**. Chasing point-efficiency meant only the already-winning
> attributes ever won. Rotating the same lift points across all twelve makes per-attribute
> allocation equal in expectation: **1.38 vs 1.37, a ratio of 0.99x where it was 2.02x**.
>
> Skills still do not fully hold at ~1.4 points — that needs the in-season economy
> (`IN_SEASON_GAIN_SCALE`, decay ranges, `TRAINING_GAIN_PERCENTAGES`), which belongs to the
> player-development system. **The allocation is no longer the cause.**
>
> **TILTED FURTHER 2026-08-14 — universals removed from the lift.** Rotating evenly equalised
> allocation (0.97x) but a second measured season showed it did NOT equalise outcomes:
> ND/IQ/FT ~+2.5 each at 85-89% of players up, the nine skills −0.8 to −1.7 at 27-39% up. Fit
> decides outcomes, not points. `ND`/`IQ`/`FT` now sit flat at their 1-point floor and the
> nine skills absorb every lift point:
>
> | | skills | universals | ratio |
> |---|--:|--:|--:|
> | fixed ND/IQ/FT lift (original) | 1.09 | 2.20 | 2.02x |
> | rotating across all twelve | 1.38 | 1.35 | 0.97x |
> | **rotating across the nine skills** | **1.48** | **1.07** | **0.72x** |
>
> **0.72 is the floor under this structure.** Universals cannot go below their 1-point floor
> and skills cannot absorb more than the available lift. Going lower needs either a cut to
> team installs (~2 points would reach 0.62) or dropping a floor to 0 — which costs −1.5/week
> ungated and should never be done.
>
> Universals still grow, just slowly: at fit 1.00 a single point nets +0.20..+0.39/week by
> class.

**Split: 50/50 for now.** Later driven by team performance, roster makeup, star-player form and
the upcoming opponent — one number, many inputs, which is why it is worth isolating now.

⚠️ **THE 12 FLOORS HOLD IN BOTH MODES.** If a roster week drops a skill to 0 to fund Bucket 3,
that attribute takes the −1.5 neglect drag *plus* year decay, and alternating becomes a sawtooth
worse than either mode alone. **The modes differ only in where the SPARE points go**, never in
whether the floors exist.

⚠️ **Accepted cost: 50/50 halves how fast identity expresses itself.** A Spread team emphasising
shooting every other week develops its SG's `SH` at half the rate of one that always does. That
is the price of hedging, taken deliberately.

### A3.5 Vision → emphasis targets

Focus-week skill emphases (3 pts each) and the team installs both modes carry:

| Vision | focus-week skills (3pt) | team installs |
|---|---|---|
| Run and Gun | conditioning*, agility | fast_breaks.offense_install |
| Spread | offense.outside, ball_handling | team_offense.install |
| Inside-Out | offense.inside, strength | team_offense.install |
| Attack | ball_handling, offense.inside | scrimmages |
| Motion | passing, offense.outside | team_offense.install |
| Full-Court Press | conditioning* | presses.defense_install, presses.offense_install |
| Man Lockdown | defense.outside, defense.inside | team_defense.install |
| Zone | defense.inside, film_study* | team_defense.install |
| Multiple | defense.inside, defense.outside | team_defense.install |
| Contain | defense.inside, defense.outside | team_defense.install, breaks |

\* **conditioning (ND) and film_study (IQ) are fit-1.00**, so Run and Gun, Full-Court Press and
Zone reach their whole roster even on a focus week. In the first draft that was luck — the
attributes were picked for flavour. It is now the reason those three visions are the most
efficiently expressed, and worth preserving.

### A3.6 Camp week (30 points)

Same two modes, +6 points. Floors stay at 1 so camp keeps its identity flavour rather than
flattening into pure development. Camp runs at `CAMP_GAIN_SCALE` 0.70 and skips decay, so every
allocation gains there — the fit constraints in §A3.3 are an IN-SEASON phenomenon only.

---

## A4. Diminishing returns on saturated team attributes

Each team-drill slot maps 1:1 to a core-8 attribute (`team_category_map`):

| slot | attribute |
|---|---|
| team_offense.install | offensive_efficiency |
| team_defense.install | defensive_efficiency |
| fast_breaks.offense_install | fb_efficiency |
| fast_breaks.defense_install | fb_opp_modifier |
| presses_traps.defense_install | pt_efficiency |
| presses_traps.offense_install | pt_opp_modifier |
| scrimmages | team_chemistry + shot_threshold + rebound_modifier |

Before allocating, read `ftd.team_attributes[attr]` and taper:

| current value | weight | slot cap (of 5) |
|---|--:|--:|
| ≤ +17 | 1.00 | 5 |
| +18 | 0.67 | 3 |
| +19 | 0.33 | 2 |
| **≥ +20** | **0.00** | **dropped, every point redirected** |

Implemented as a linear ramp (§`_install_weight`) rather than the drafted 0.75/0.5/0.25, which
was flagged as a proposal. The weight is a per-slot **cap**, not just an on/off filter — as a
filter alone, a team at +18 still took full points into an attribute two off its ceiling, which
is most of what the taper exists to stop.

Freed points cascade: next-priority slot in the same vision → `scrimmages` → raise a player-drill
floor 1→2 (never wasted; +2.0 → +2.5 expected is still positive).

**ALLOCATION-SIDE ONLY — no engine change.** The clamp at `TEAM_ATTR_CLAMPS` already makes a
+20 attribute gain nothing (it adds `delta`, then clamps straight back), so those points are
silently wasted today. This only stops *spending* them. Nothing about the gain curve, the
clamp, or the EOG bands moves.

This also makes allocation **state-dependent**: a team that has maxed its identity attribute
naturally stops over-training it and spreads elsewhere — better emergent behaviour than a
static table.

---

## A5. Drawbacks are EMERGENT — no explicit penalties

A Bobby Knight team is bad in freelance because he never coaches it and neglect erodes what is
untended — not because a malus is applied. Decided 2026-08-12.

⚠️ **Calibrated consequence:** on the *team*-attribute side, neglect is deliberately mild
(a few points a season, probability-gated) because an earlier version floored every team
(discipline −91.6/season). So team-drill drawbacks are a subtle tilt, and EOG results dominate.
On the *player* side a 0 is genuinely punishing (§A3.1) — but the floors mean CPU teams never
take that hit. **Net: identity reads mainly as what a team is GOOD at.** If drawbacks need more
bite later, raise `NEGLECT_DECAY_CHANCE_DEFAULT` for CPU teams only — still emergent, no
explicit penalty.

---

## A6. Deferred — opponent game-planning

Teams should also plan for the opponent: dial up fast-break defense against a running team,
outside defense against shooters. Target blend ≈ **75% identity / 25% opponent**.

**Deferred deliberately.** The 75/25 blend cannot be tuned without first seeing what 100/0
produces; it is a modifier over this table, not a rewrite; and it needs a check this design has
not done — whether a CPU team can even see its next opponent's tendencies at training time.

---

## A7. Build order

1. ✅ **SHIPPED** `840c685a2` — one team-wide plan (deleted the position-group loop)
2. ✅ **SHIPPED** `d3efecd1b` — 1 of 16 coaching focuses, derived per (franchise, team, season,
   week) rather than drawn, because pool workers each seed their own `training_rng` and an RNG
   draw would not replay. Measured cost −0.14 ± 0.14/player/week: **not distinguishable from
   zero**, contrary to my prediction that it would meaningfully hurt.
3. Identity → allocation, TWO MODES (§A3.4) + saturation taper (§A4)
4. Re-measure CPU player development — the ~+38.7 arc will have moved
5. Re-check EOG bands against a season of the new allocation
6. *Later:* coach identity (major/minor), then opponent game-planning

## A8. Open questions

1. ~~Is identity better expressed through systems than bodies?~~ **RESOLVED by §A3.4** — both,
   alternating. The two modes exist because neither lever alone reaches the whole roster AND
   says something about identity.
2. Camp at +6 (§A3.6) — confirmed, or raise floors to 2 instead?
3. The taper curve in §A4 (0.75/0.5/0.25 across +17/+18/+19) is a proposal, not measured.
4. **The 50/50 mode split is arbitrary.** It is the dial future logic turns (performance,
   makeup, star form, opponent), so it should be a single named constant from day one.
5. **Does alternating beat a steady middle?** A skill attribute gets 3pt half the time and 1pt
   the other half; whether that outperforms a steady 2pt is measurable and untested. The
   floors mean neither option risks the −1.5 neglect drag, so this is a tuning question, not
   a safety one.

---

# PART B — UNBUILT SURFACES

Migrated from `cpu_team_identity_spec.md` 2026-08-15. **None of this is implemented.** Check the
system doc's ▶ SURFACE STATUS table before building any of it — two proposals in the original
spec had already been measured and rejected by the time anyone read them.

## B1. Playbooks — NOT identity-driven today

⚠️ **`cpu_playbook_customization.py` contains ZERO references to identity or vision.** It builds
from `_classify_focus_strengths(position_players)` — roster shape alone. Coverage is also scoped
to *the teams the user is scheduled to play* (`build_user_schedule_cpu_playbook_groups`), so
CPU-vs-CPU games use default playbooks: **8/128 teams customised at week 2, 19/128 at week 15**.
That scoping is deliberate, not a bug.

Two things per vision: **which play families** and **how concentrated**. Concentration from the
`breadth` signal in three bands — low breadth → few plays funnelled to the focal scorer.

| Vision | Play families | Concentration |
|---|---|---|
| Run and Gun | fast breaks weighted, motion base | medium |
| Spread | outside sets, motion | **low** (many plays) |
| Inside-Out | post family — Base, Movement, Flash | **high** personnel, **low** play conc. |
| Attack | drives, iso, pick-and-roll | medium-high |
| Motion | motion base, balanced sets | medium |

**Inside-Out is the important case** — concentrated personnel, diverse *plays*: feed one post
scorer through five different actions, reaching the EOG `offensive_efficiency` reward tier
instead of paying a permanent scouting tax.

Defensive visions also carry play sets — Full-Court Press should hold 3–4 press variants, since
the EOG concentration penalty applies to press plays too.

> ⛔ **The spec's "concentration caps must be lifted" is REJECTED** (decided 2026-08-12). The
> intended ceiling for a single play's share of a normal playbook stays at **25%**. See the
> system doc §9 for the schedule (`_set_play_percentages`: 1 play→100%, 2→55%, 3→45%, **4+→20%**)
> and why a literal 25% cap cannot hold below 4 plays.

## B2. Rotation size — UNBUILT

No `rotation_size` exists anywhere in `BackEnd/`. Driven by **depth**, not vision, with one
vision override:

| Capable backups | Rotation |
|---|---|
| 0–2 | ~8 players |
| 3–4 | ~9 |
| 5–6 | ~10–11 |

Full-Court Press forces a minimum of 9 regardless — you cannot press forty minutes off seven
men. That is the vision's cost appearing on a third surface.

⚠️ **`starter_bench_gap` IS NOT DEFINED IN THE CODEBASE** — it appears only in a `db_utils`
comment. A working definition and its three arguable choices are in `bugs.md`. Measured on a
live league it runs 2.0–29.2 (mean 11.1), so the spec's 13/19 band edges put **75% of the league
in one band** and were cut against a different population.

> **Decided 2026-08-12:** use a **within-team** comparison — how many bench players are within X
> of the starter they would replace — not an absolute `RT ≥ 50` bar. A gap between two players on
> one roster survives any recalibration; an absolute threshold does not. **Cadence: every five
> weeks**, aligned to the §B4 re-evaluation, so there is one clock rather than two.

⚠️ May not be buildable in isolation: `CPU_Team_Rotation_System.md` §8 attributes current depth
(6.69 players above 8% of minutes, against a target of 8–11) to the **fatigue economy**, not the
selector. A `rotation_size` parameter may not move minutes at all.

## B3. Starting five and user teams — UNBUILT

**Starting five:** established at training camp, **persisted**, used every game. This is new
state — today the five is re-derived from eligibility at each rebuild.

> **The frontend also needs handling.** Browser bulk sims call `/api/autoset-lineup` for both
> teams on every quarter after the first, so a designated five currently survives only one
> quarter. The override has to reach that path, not just the backend selector.

**User teams:** the effective-talent floor applies to the user too — automatically in sim, and as
a **warning** in turn-by-turn. Crossover is the right trigger precisely because it is rare: it
fires only when something is objectively wrong rather than nagging.

> ⛔ **Substitution policy is CLOSED — two mechanisms measured, neither pays.** The NG pull/return
> hysteresis pair cost ~1 point a game and was stripped. The redirect to the selector objective
> weight `w` was then tested conditioned on `starter_bench_gap`: top-heavy and shallow bands came
> back at **−1.56 and −1.22**, same sign, differing by 0.34 (≈ ⅛ of one SE), where the spec
> predicts *opposite* signs. Both writeups land in the same place: **the lever for changing CPU
> rotation behaviour is the FATIGUE ECONOMY, not the selector or the gate.** Full numbers in
> `bugs.md`. Do not reopen this with another parameter grid.

## B4. Five-week re-evaluation — UNBUILT

`identity_is_current` keys on `assigned_season` only — no week term — so a team keeps its vision
all season even as its roster drifts. `assigned_week` is already persisted for whenever this is
built.

Every five weeks. Switching requires something **compelling**, from two inputs:

```
results     are we failing?            1-9 switches even if fit is fine
fit gap     is another vision better?  covers roster drift AND a bad initial pick
```

**The switch threshold rises with the week.** A week-5 change costs five weeks of training; a
week-20 change is nearly pointless with six weeks left. A rising bar kills late switches without
a special rule and captures the sunk cost directly — collapsing commitment and hysteresis into
one thing.

**Penalties are emergent, not designed.** Player attributes do not transfer, and team attributes
built under the old identity decay once unused.

⚠️ **Weakest-specified surface here** — two named inputs and no formula. Needs design, not just
implementation.

## B5. Implementation notes

**Tunable Constants — document as one coupled block:** fit weights (both tables), frozen scale
constants, flat constants (Motion +0.60, Contain −0.50), fuel costs and capacity terciles,
softmax temperature, slider weight vectors. All are calibrated against the pool the signals were
measured from, so **a pool migration should break a regression test, not drift the league
quietly** — same pattern as `_CPU_REFERENCE_BASE` / `test_cpu_reference_training.py`.

⚠️ That risk is now REAL: `SIGNAL_SCALE` and `FUEL_CAPACITY_BOUNDS` were fitted before the
attribute recalibration and the second −2in height shift. Re-derive before trusting the vision
distribution.

**Validation is downstream, not distributional.** Different aggregation forms produce
near-identical population splits while disagreeing about a third of the teams. The real test is
behavioural: do press-identity teams actually press effectively, and do outside-identity teams
outshoot the league?

✅ **Done since the spec was written:** `autoset_strategy_settings` frozen at roster level
(`36964422d`); the unreachable `cum_nd > 350` branch removed.

## B6. Open items from the original spec

| # | item | status |
|---|---|---|
| 1 | Slider semantics — is `offense` motion↔set, `defense` man↔zone? | ✅ **RESOLVED** — ratios confirmed, code already matched. System doc §3 |
| 2 | Slider weight vectors ("my proposal, not measured") | ✅ **ACCEPTED as authored** 2026-08-12, including the Motion-ordering quirk |
| 3 | Playbook concentration caps | ✅ **RESOLVED** — stay at 25%, lift rejected |
| 4 | Backup-quality bar | ✅ **RESOLVED** — within-team comparison, 5-week cadence |
| 5 | Vision persistence, and do users get one? | ✅ **RESOLVED** — `ftd.identity`; users get **no** identity |
