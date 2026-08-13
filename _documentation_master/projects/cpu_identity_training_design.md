# CPU Identity-Driven Training — DESIGN (not built)

**Status: design only, 2026-08-12. No code written.** Review this before implementing.

Supersedes `cpu_team_identity_spec.md` §6, which was written against a CPU training path that
does not work the way the spec assumed.

---

## 1. The defect this fixes

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

## 2. Weekly coaching focus — RANDOM for now

Each CPU team draws **one of 16** leaves per week, from **`training_rng`** (never the global
stream — see the per-subsystem RNG rule).

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
> planned, not scoped here. Focus choice is random so the ALLOCATION logic below can be
> measured without a second moving part.

---

## 3. Allocation — 12 floors + 6 offensive + 6 defensive = 24

### 3.1 Why floors exist (this is the load-bearing constraint)

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

### 3.2 Base

All 12 never-zero slots start at **1** (= 12 pts). `breaks` and the 7 team drills start at **0**.

### 3.3 Offensive vision spends 6

| Vision | +2 | +1 | +3 (team drill) |
|---|---|---|---|
| Run and Gun | conditioning | agility | fast_breaks.offense_install |
| Spread | offense.outside | ball_handling | team_offense.install |
| Inside-Out | offense.inside | strength | team_offense.install |
| Attack | ball_handling | offense.inside | scrimmages |
| Motion | passing | offense.outside | team_offense.install |

### 3.4 Defensive vision spends 6

| Vision | +2 | +1 | +3 (team drill) |
|---|---|---|---|
| Full-Court Press | presses.offense_install (+2) | conditioning | presses.defense_install |
| Man Lockdown | defense.outside | defense.inside | team_defense.install |
| Zone | defense.inside, film_study | — | team_defense.install (+2) |
| Multiple | — | defense.inside, defense.outside, film_study | team_defense.install |
| Contain | team_defense.install, breaks | defense.inside, defense.outside | — |

### 3.5 Worked examples

**Inside-Out / Zone** — a post team that packs the paint
`SC 3 · ID 3 · film_study 3 · team_off 3 · ST 2 · team_def 2`, all else 1, fb/scrimmages/presses/breaks 0 = **24**

**Run and Gun / Full-Court Press** — the most physically demanding pairing
`conditioning 4 · fb.off 3 · presses.def 3 · presses.off 2 · AG 2`, all player drills 1, team_off/team_def 0 = **24**

That `conditioning 4` is the **only** 4 the table can produce, and only for this pairing — which
is exactly when it is earned. That team never installs team offense or defense: a legible
weakness, entirely inside the safe-to-zero block.

### 3.6 Camp week (30 points)

Each vision spends **9** instead of 6, same shape scaled. Floors stay at 1 so camp keeps its
identity flavour rather than flattening into development.

---

## 4. Diminishing returns on saturated team attributes

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

| current value | slot treatment |
|---|---|
| ≤ +16 | full points |
| +17 to +19 | taper 0.75 / 0.5 / 0.25 |
| **≥ +20** | drop the slot, redirect every point |

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

## 5. Drawbacks are EMERGENT — no explicit penalties

A Bobby Knight team is bad in freelance because he never coaches it and neglect erodes what is
untended — not because a malus is applied. Decided 2026-08-12.

⚠️ **Calibrated consequence:** on the *team*-attribute side, neglect is deliberately mild
(a few points a season, probability-gated) because an earlier version floored every team
(discipline −91.6/season). So team-drill drawbacks are a subtle tilt, and EOG results dominate.
On the *player* side a 0 is genuinely punishing (§3.1) — but the floors mean CPU teams never
take that hit. **Net: identity reads mainly as what a team is GOOD at.** If drawbacks need more
bite later, raise `NEGLECT_DECAY_CHANCE_DEFAULT` for CPU teams only — still emergent, no
explicit penalty.

---

## 6. Deferred — opponent game-planning

Teams should also plan for the opponent: dial up fast-break defense against a running team,
outside defense against shooters. Target blend ≈ **75% identity / 25% opponent**.

**Deferred deliberately.** The 75/25 blend cannot be tuned without first seeing what 100/0
produces; it is a modifier over this table, not a rewrite; and it needs a check this design has
not done — whether a CPU team can even see its next opponent's tendencies at training time.

---

## 7. Build order

1. Collapse CPU training to one team-wide plan (deletes the position-group loop)
2. Random focus from the 16, on `training_rng`
3. Identity → allocation table (§3) + saturation taper (§4)
4. Re-measure CPU player development — the ~+38.7 arc will have moved
5. Re-check EOG bands against a season of the new allocation
6. *Later:* coach identity (major/minor), then opponent game-planning

## 8. Open questions

1. **Roughly half of each vision's emphasis lands on team drills** (the +3s). Team attributes
   are probability-gated, player attributes are not, so those points are "cheaper" in expected
   value. Is identity better expressed through *systems* than *bodies*?
2. Camp at 9+9 (§3.6) — confirmed, or raise floors to 2 instead?
3. The taper curve in §4 (0.75/0.5/0.25 across +17/+18/+19) is a proposal, not measured.
