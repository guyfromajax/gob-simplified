# Coord-Consumer UESS Audit — `player.coords` vs render

**Question:** which game-logic consumers decide from `player.coords` (animator row-end, set by `apply_coords_from_animations_list`) instead of the emitter's rendered coord — the same defect that mis-scored 2PT/3PT classification? (2026-07-05, 3 parallel traces + probes.)

## Root cause (one line)
`ShotManager.resolve_shot` and rebound logic read `def_lineup[pos].coords` / `player.coords` = **animator row-end**, which diverges from the emitter's **interrupted** shoot-step render coord (§9.5: only the gate/shooter reaches full destination; others render mid-move). The shipped classification fix synced **only the shooter** (`_uess_terminal_shoot_coord` → `roles["shot_spot"]`); **defenders and rebounders were left on the divergent animator coords** → mixed-frame decisions.

## Systemic question: RESOLVED FAVORABLY
`sync_lineup_coords_from_turn` (shared.py:3589-3609) writes the **emitted** `animation_steps[-1].end.coords` and it **takes precedence** over animator finals for migrated turns → `final_coords`/BIP/SIP/HCO carry-forward propagate the render coord. **The desync is per-shot within a turn, NOT compounding across turns.** Only leak: legacy turns with no `animation_steps` (already logged, shared.py:3616).

## Ranked holes (measured where cheap)

| # | Risk | Location | Decision flipped | Coord read | Impact |
|---|---|---|---|---|---|
| 1 | ✅ **FIXED** | shot_manager.py:773/803 (HCO-motion contest) | contested↔uncontested → block path + shot quality | ~~defender `.coords` = animator row-end~~ → now emitted render coord | **~6% per-defender flip; ~2% aggregate `has_contest` drop** (over-contest removed). Fixed 2026-07-05 via `_uess_sync_emitted_shot_coords` (syncs ALL players to emitted shoot-step coords before resolve_shot; HCO/FT/FCP). Regression-clean. |
| 2 | ✅ **FIXED** | shot_manager.py:809-816 (Covert Release) | block never fires on contested CR | ~~STALE pre-race `def_lineup.coords`~~ → now honors CR's render-matched `roles["defender"]` | Fixed 2026-07-05: CR stamps `roles["fb_geometry_contest_resolved"]`; `resolve_shot` honors `bool(defender)` instead of the stale coord loop → block fires on contested CR. Regression-clean; `test_covert_release_drive_resolution` passes. |
| 3 | ✅ **COVERED by #1** (severity revised) | shared.py:1583/1670 (`select_rebounder_by_score`) | ~~possession~~ → individual rebounder **attribution** | candidate `player.coords` — now render-synced (selection runs inside `resolve_shot`, after #1's sync) | **Measured: ~75% individual-rebounder flip, ~0% possession flip** (box-out/team weighting is possession-stable). #1 routed selection through render-synced shoot-step coords. Bounce-step coords (agent's suggestion) are circular — post-crash positions depend on the selection. No separate fix needed. |
| 4 | ✅ COVERED by #1 | shared.py:1835 (near-bounce pool) | eligible rebounder set | `player.coords` — now render-synced | same sync covers it |
| 5 | MED-HIGH | shot_manager.py:146-162 (zone matchup) | zone contest + double-team | `zone_defender_assignments_by_step` built from animator coords (animator.py:1912) | zone HCO contest y/n |
| 6 | MED | shared.py:862 / 892 (OREB putback def / OTB foul) | putback contest / OTB foul y/n | defender `.coords` = animator/prior-turn | bounded, low-freq |
| 7 | MED | turn_manager.py:3407/5585 (zone `defense_score`) | zone defender → `player_d` | `HCO_STRING_SPOTS[shooter_spot]` (named, not coords) | margin-only |

## Immune / correct pattern (already render-synced)
- **Steal-FB (`after_steal_fast_break.py`), HCT (`dynamic_hct_shot.py`), universal FB drive-step (`fb_drive_resolution.py`)** — compute render ends once and write `player.coords = rendered ends`; contest coord == render coord **by construction**. **This is the pattern to copy.**
- **Man set-play & Final Turn contest** — assignment-based (`has_contest = bool(defender or second_defender)`), not coord-compared.
- **Cross-turn carry-forward** — render-synced (precedence rule above).
- **Bounce origin / block spot / block magnitude** — render-synced via `shot_spot`, or attribute-only.

## Fix architecture (unified)
✅ **DONE for #1:** the shipped shooter-only pre-pass was generalized to **all players** — `_uess_sync_emitted_shot_coords` (phase_resolution.py) runs the RNG-neutral emitter pre-pass once and stamps the emitted shoot-step `end.coords` onto **every** `player.coords` before `resolve_shot` (HCO/FT/FCP call sites). The contest coord loop now reads render-synced defenders. Frame-safe: `player.coords` and emitted coords are both display orientation (`_normalize_animation_coords_to_runtime_home` is a pass-through). Mirrors the Steal-FB/HCT pattern.

**NOTE — #5 is NOT covered by this:** the zone matchup reads `zone_defender_assignments_by_step` (a separate structure built from animator coords in animator.py:1912), not `player.coords`. Still open.

Separate handling:
- **#3/#4 rebounder** — relevant coord is the **post-shot pre-bounce** step (needs the outcome), not the shoot step → route rebound distances through the emitted `[bounce]` sub-step coords, not live `player.coords`.
- **#2 Covert Release** — either run `apply_coords` (currently skipped, phase_resolution.py:2028) or stop `resolve_shot` discarding `compute_fb_shot_geometry`'s render-matched contest.

**Caveat:** the pre-pass ~98% reproduces the late render (early/late context divergence, per Shot_Classification_UESS_Fix_Scope.md), so this lands ~94-98% render-synced, not exact. Same residual class as classification.

## Progress
- ✅ **#1 contest defenders** — FIXED (`_uess_sync_emitted_shot_coords`, HCO/FT/FCP). Contested-rate ~98.7%→96.7%; regression-clean.
- ✅ **#3/#4 rebounder + near-bounce pool** — COVERED by #1 (selection runs after the sync); severity revised (attribution, not possession — 0% possession flip measured).
- ✅ **#2 Covert Release block** (HIGH) — FIXED (`fb_geometry_contest_resolved` flag; `resolve_shot` honors CR's render-matched defender). Regression-clean.
- 🟡 **#5 zone matchup** (MED-HIGH) — **DEFERRED as accepted gap** (2026-07-05). Fix = rebuild `zone_defender_assignments_by_step` from render coords via `assign_all_zone_defenders`, which has load-bearing home/away orientation handling (animator.py:1910-1944) → high away-offense risk. Measured impact is second-order: zone contest ~95% stable + coarse zones → primary defender (hence `has_contest`) rarely flips; residual is double-team/attribution only. Risk/reward inverted vs the low-risk `player.coords` syncs of #1-#4.
- 🟡 **#6 putback defender / OTB foul** (MED) — putback reads the render-matched bounce origin and nearest live defender coords; that distance now affects graded contest strength through 11 and contest eligibility beyond 11. OTB foul remains low-frequency/bounded.
- 🟡 **#7 zone defense_score** (MED) — deferred with #5 (named-spot based; margin-only effect on `defense_score`).

## Update 2026-07-22 — full-sim HCO shot-frame hole closed

The original #1 fix was complete only for animated turns. CPU/full simulations set
`_is_full_simulation`, causing `Animator.skeleton_to_animations()` to return `[]`;
`_uess_sync_emitted_shot_coords()` then returned `None`, and its fallback synchronized only the
shooter. HCO shot contest therefore compared the current skeleton release coord with stale defender
`Player.coords`—the 63-game week diagnostic exposed this as an abnormal undefended rate.

HCO now freezes a `ShotAttemptGeometry` before `resolve_shot()`:

- animated turns snapshot the emitter-synchronized shot frame;
- full sims snapshot the final shot step's sim-safe `_step_state.defense` grid (and compute a final
  grid only when a late rewrite left the step unstamped);
- shot classification/contest receives the immutable value explicitly and never falls back to
  mutable defender coords once the contract exists.

This is deliberately a shot-attempt slice, not yet a universal stop-state migration. Its value-object
shape is reusable for the broader resolve-once work in `hco_roles_audit.md` after shot behavior is
validated.

**Accepted-gaps rationale:** #5-#7 are all *attribution / second-order shot-difficulty* effects, not binary-outcome (contest/possession) flips. The four HIGH holes (#1-#4) that flip actual outcomes are closed. Revisit #5 if a zone-double-team or zone-FG% anomaly surfaces in tuning.

The 4 HIGH fixes shift FG%/contest → land before shot-system re-tuning ([[project_shot_system_tuning]]).

---

# Frontcourt / backcourt consumers (2026-09-05)

**Question:** §9.5 names "over-and-back / frontcourt / shot-clock reads" alongside contest and rebound, but the audit above only covered the shot family. Which sites decide frontcourt/backcourt status, and do they read the emitted `end.coords[p]` or something else? (Audit only — no behaviour changed.)

## Root cause (one line)
`_recover_defense_targets` (dynamic_hct.py:1848) asks "is this defender stranded in the backcourt?" of `targets[pos]["x"]` — the beat's **authored destination** — while the render-faithful coord (`def_coords[pos]`, which `_segment`:2044 emits verbatim as the step's `def_end`) is in the same scope and unused for that test.

**The over-and-back family itself is clean.** Every consumer of the canonical `over_and_back.py` predicates reads a rendered coord. The exposure is one defensive-positioning overlay plus a duplication surface: the half-court predicate is written out **five separate times** across the engine, and the copies are load-bearing in four of them.

## Ranked holes (measured where cheap)

| # | Risk | Location | Decision flipped | Coord read | Impact |
|---|---|---|---|---|---|
| F1 | **HIGH** | dynamic_hct.py:1848 (`_recover_defense_targets`) | defender is "stranded" → redirected to the nearest unguarded offender **and** promoted to the `sprint` move archetype (`_defender_move_archetype`:1887) | `targets[pos]["x"]` — **destination**, from `play.defense_targets(...)` / `_defense_targets(...)` at 1913-1917. The rendered end for the same beat is computed *after*, at 1931 (`_interrupted_coord`) | **Measured 4.8% and 4.5% per-defender flip** (two independent samples: 6 games / 1,920 verdicts, 12 games / 3,550 verdicts). **18.3% of FC-established recovery calls** compute a different stranded *set*. Directional, not noise: the destination read sees 6.5% / 5.2% of defenders in the backcourt where the rendered prior end sees 10.7% / 8.8% — it **under-detects by ~40%**, so the recovery overlay silently fails to fire for defenders the FE is actually showing in the backcourt |
| F2 | MED-HIGH | dynamic_hct.py:1859 (same function, "covered" inference) | which offender each recovered defender picks up — and whether he falls through to the key help spot instead | `_euclid(targets[dpos], off_coords[op])` — a **destination** (`targets[dpos]`) compared against a live off coord. Mixed frame within one expression; the sibling read 9 lines later (1868) uses `def_coords[pos]`, the render coord, for the same class of question | **Measured 11.7% of 16,835 defender/offender pairs flip** the `<= DEFENSE_RECOVERY_GUARDED_RADIUS` (8.0, :1816) test between the destination and the render coord. Second-order — it reshuffles assignment, not possession |
| F3 | MED | dynamic_hct.py:819 `_crossed_half_court` / :823 `_in_backcourt` | **nothing today** — verified dead in production | coord-agnostic (takes `x` as a param), so no provenance of its own | Latent, not live. Repo-wide the only importer is `tests/test_dynamic_hct_violations.py`:5-6. That is the trap: the duplicate is **pinned by its own tests**, so the canonical pair in over_and_back.py:27,31 could change semantics and this copy plus its green tests would sit there unchanged, ready for the next caller in a 3,400-line module to reach for the local name. Same shape as the `_ag_grid_per_game_sec` divergence in findings §12a |
| F4 | LOW | covert_release_step_emitter.py:1369 (`_ball_crossed_midcourt_toward_basket`) | whether the "Great Stop!" callout, stinger and hold are emitted | **Compliant read** — `ball_spot` is `outcome_step["end"]["coords"][...]` (:1589), the emitted end. Listed only as a **fifth hand-written copy** of the predicate | Presentation only; no outcome. Duplication risk, not a §9.5 breach |

**Not measured (and why):** F3 has no live decision to flip. F4's read is already the emitted end, so there is nothing to compare it against. F1/F2 were measurable because the divergent and the correct coord are both in scope at the call, so a wrapper can evaluate both without perturbing the sim.

**Measurement method (F1/F2), for reproduction.** Monkeypatch `dynamic_hct._recover_defense_targets` with a wrapper that, before delegating unchanged to the real function, evaluates `in_backcourt(targets[pos]["x"])` against `in_backcourt(def_coords[pos]["x"])` for all five positions, then drive `simulate_quarter` over N games with `hc_trap`/`fc_press` enabled on both teams (without them, HCT turns never route and the function is never reached with `frontcourt_established=True` — a first pass at defaults recorded 0 calls in 371 turns). Read-only: the wrapper returns the real function's result. `def_coords` is the right comparator because `_segment`:2044 serialises it directly as `def_end`.

## Immune / correct pattern (verified render-synced)
- **The whole over-and-back rule path in `dynamic_hct`** — this is the pattern to copy. `update_frontcourt_established` on the ball handler (:3097) reads `bh_xy`, which is `off_coords[bh_pos]` written from `_interrupted_coord` at :2632-2635. The **10-second violation** (:3112-3116) and the over-and-back **turnover** (:3379) inherit that same coord. `should_hold_instead_of_backcourt_pass` (:3211) reads `off_coords[receiver_pos]`, and the receiver is `exclude`d from the beat's movement (:3346), so his coord *is* his rendered end.
- **Catch-spot frontcourt establishment (:3373) and the over-and-back turnover read (:3379)** — both run *after* `_pass_segment` is built at :3349, on the same `off_coords` the segment serialised. `_gate_offense_backcourt(skip={receiver_pos})` at :3348 deliberately exempts the receiver so the ratchet cannot suppress detection — the comment at :2364-2367 says so explicitly. This is the sharpest correct instance in the file: someone already reasoned about exactly this failure mode.
- **The backcourt re-entry ratchet** (over_and_back.py:130 via `_gate_offense_backcourt`:2371) — reads `off_coords`, and mutates it *before* `_segment` runs (`_append_loop_segment`:2393 calls the gate first). The clamp to `HALF_COURT_X` therefore becomes the emitted end rather than diverging from it.
- **Cross-half urgency** — dynamic_hct.py:556 and fcp_offball_attack.py:328 both read `off_coords[pos]["x"]`, the prior beat's interrupted end (FCP's are written through `interrupted_fn=_interrupted_coord`, passed at dynamic_hct.py:2616).
- **Post-steal over-and-back guard** (skeleton_step_emitter.py:4082,4087) — reads `stealer_start = start_coords[stealer_id]` (:4067), the prior step's emitted end, and clamps `stealer_end_x` — the **end**, not a destination. Render-truthful by construction.
- **PG midcourt clamp** (reset_step_helper.py:90,92 and transition_bridge.py:102,104) — reads `start_coords[bh_id]` (:163, :498), the prior emitted end. It constrains a *target*, which would ordinarily leave the guarantee unenforced at render — but the PG is the **gate player** on both steps (`end_coords[pg_id] = dict(pg_target)`, reset_step_helper.py:320 / transition_bridge.py:640, with `t` sized to his own travel time at :306 / :626), so he reaches it exactly. The clamp is honoured in the render. Correct, but only because of the gate; it would become a hole the moment either step stopped gating on the PG.
- **`over_and_back.py` itself** — the canonical predicates (:27, :31, :48, :59, :130) take `x` as a parameter and hold no coord source. Provenance is entirely the caller's responsibility, which is why this audit is a call-site audit.

## Predicate duplication surface (F3's real scope)
`crossed_half_court(x, is_away_offense)` — `x <= 50 if is_away_offense else x >= 50` — is written out five times:

| Copy | Live? | Enforced to agree? |
|---|---|---|
| over_and_back.py:28 (canonical) | yes | — |
| dynamic_hct.py:820 | **no — dead in production** | only by `tests/test_dynamic_hct_violations.py`, which tests the *copy* |
| covert_release_step_emitter.py:1369 | yes (announcement gate) | no |
| skeleton_step_emitter.py:4082,4087 | yes (post-steal clamp) | no — and inlined per-branch, not extracted |
| reset_step_helper.py:90,92 + transition_bridge.py:102,104 | yes (PG clamp) | no — and these two are byte-near-identical functions in two files |

All five agree today (verified by reading each). Nothing enforces it.

## Failing tests — diagnosis only

Both failures are in the **test**, not the engine. Neither is evidence of a §9.5 defect, and the third lead's premise does not survive contact.

**`test_cross_half_urgency_target_is_frontcourt_side` — `assert 51 <= 0`.** Not the away mirror. The test sets `is_away_offense=False` and passes `flip_fn=lambda xy: xy`, so the mirror is never exercised. The mock supplies `randint.side_effect = [55, 0]` in `[x, y]` order, but `cross_half_urgency_target` draws **y first** (`:90`, the ±8 jitter) and **x second** (`:93`). Instrumented call order, verified: `[(-8, 8, 55), (51, 57, 0)]` → `y = 25 + 55 → clamped 45`, `x = 0`. Swapping the two side-effect values makes it pass. The away mirror is in fact **correct**: x is drawn in `[51, 57]` and then flipped through `_flip` → `get_away_player_coords` (dynamic_hct.py:385-387), giving `[43, 49]`, which is the away offense's attacking half (away attacks toward x=0).

**`test_after_grace_uses_passer_awareness` — `assert not True`.** A boundary off-by-one, and the test contradicts itself. `passer_over_and_back_threshold` is `0.8·PS + 0.2·CH`, and `passer_commits_over_and_back_pass` returns `roll > threshold` (strict). Both halves of the test set `roll == threshold` but assert opposite outcomes: the first half (PS=CH=40, roll=40 → threshold 40.0) expects a **hold** and passes; the second (PS=CH=99, roll=99 → threshold 99.0) expects a **pass** and fails, because `99 > 99.0` is False → no commit → hold. Verified by direct call: `commits(roll=99) = False`, `commits(roll=100) = True`. Either the test should roll 100, or the predicate should be `>=` — but the two halves cannot both be right as written, so this needs an intent decision (at PS=CH=99 the current code yields a 1-in-100 mistake rate; `>=` would make it 2-in-100). **Not diagnosed here:** which of the two is the intended rule.

## Enumeration — greps, and every hit accounted for

Candidate discovery, run against `BackEnd/**/*.py`:

```
rg -in 'frontcourt|backcourt|front_court|back_court' BackEnd/ --glob '*.py'      # G1: 208 hits / 15 files
rg -n  '_?crossed_half_court|_?in_backcourt'         BackEnd/ --glob '*.py'      # G2: definitions + call sites
rg -n  'CROSS_HALF_URGENCY'                          BackEnd/ --glob '*.py'      # G3
rg -n  'HALF_COURT_X'                                BackEnd/ --glob '*.py'      # G4
rg -n  'frontcourt_established'                      BackEnd/ --glob '*.py'      # G6
rg -n  'is_over_and_back_pass|should_hold_instead_of_backcourt_pass|gate_offense_backcourt_reentry|update_frontcourt_established|cross_half_urgency_target' BackEnd/ --glob '*.py'   # G7
rg -n  '\bx\b[^=!<>]{0,24}(>=|<=|>|<)\s*50\b|50\s*(>=|<=|>|<)[^=]{0,24}\bx\b|100\s*-\s*.*\bx\b' BackEnd/engine/ BackEnd/utils/ --glob '*.py'   # G8
```

G1-G7 find only sites that go through the canonical helpers or the name. **G8 is the one that matters for exhaustiveness** — it catches half-court tests written inline against the literal 50, which is how three of the five duplicates are written and which no name-based grep would surface. G8's 22 hits are accounted for individually:

**In scope, kept:** over_and_back.py:28 · dynamic_hct.py:820 · covert_release_step_emitter.py:1369 · skeleton_step_emitter.py:4082,4087 · reset_step_helper.py:90,92 · transition_bridge.py:102,104.

**Ruled out, with reason:**
- covert_release.py:159,181 · fcp_offball_attack.py:97 · fcp_pf_c_zone.py:28 · covert_release_step_emitter.py:468,1132 · shared.py:1549 — all `100 - x` **orientation flips** (home↔away mirroring). They transform a coord; they do not test half-court status.
- dynamic_hct.py:832 (`_past_primary_safe_area`) · dynamic_hct.py:1017 · dynamic_hct_shot.py:1207 — the **PSA / Attack Basket Area** line at x=64/36, not the half-court line. Different rule (§7 goal achievement, D21/D22).
- shot_micro_movements.py:456 — `x < 50.0` is a **tie-breaker** inside `_infer_away_offense_from_display_coord`, used only when the two rim distances are within 0.5. It infers which *frame* a coord is in, not whether a player is in the frontcourt.

Hits from G1 that name "backcourt" but decide something else, also ruled out:
- final_turn_pacing.py:209-210 with `BACKCOURT_X_HOME = 71.0` / `BACKCOURT_X_AWAY = 29.0` (:27-28) — **not the half-court line** despite the constant name; it is a walk-up pacing band at x=71/29. Worth flagging separately: it reads `prior_turn["final_coords"][bh_id]` (:203-204), which per the systemic finding at the top of this document is the render-synced source, so it is compliant on its own terms.
- getback_selection.py:126 `_backcourt_distance_from_basket` — a **distance from basket**, used to rank getback eligibility. No half-court test.
- fcp_inbound_release.py:58 `_occupied_backcourt_tiers` — partitions by **y** into upper/center/lower tiers (:66). Named "backcourt" because the FCP inbound happens there; no x comparison.
- hct_trap_plays.py:122,126 · dynamic_hct_step_emitter.py:8 · phase_resolution.py:11256 · fb_geo_helpers.py:78 · shared.py:3298 · transition_bridge.py:930 · covert_release_step_emitter.py:21,1216 · constants/__init__.py:474,476,499 — **comments and docstrings only**, no executable comparison.
- The remaining G1 volume is concentrated in dynamic_hct.py (125 hits) and over_and_back.py (24) and is the parameter/variable name `frontcourt_established` threaded through signatures, plus prose. Every executable use is enumerated by G6/G7 above and appears in the table or the immune list.

## Progress
- 🔴 **F1 stranded-defender read** (HIGH) — OPEN. Direct §9.5 violation with a measured, directional flip rate. The render coord (`def_coords[pos]`) is already the function's second parameter, so the read is a one-expression change; what needs deciding first is **intent**, since the docstring (:1829-1831) explicitly frames the question as "the *play's own target* still sits in the backcourt". If that framing is deliberate, §9.5 and this function disagree about what is being asked and the spec or the docstring has to give. Flagging, not resolving — this audit does not fix.
- 🔴 **F2 "covered" inference** (MED-HIGH) — OPEN, and should move with F1: it is the same function, the same mixed frame, and 1868 nine lines below already reads the render coord for a near-identical distance question.
- 🟡 **F3 dead private duplicate** (MED) — OPEN as a latent trap. No live consumer; the risk is entirely that the copy is test-pinned and therefore looks maintained.
- 🟢 **F4 announcement gate** (LOW) — reads the emitted end; carried only on the duplication list.
- ✅ **Over-and-back rule path, ratchet, cross-half urgency, post-steal clamp, PG midcourt clamp** — verified compliant; see the immune list for the coord and line behind each.
- ⚪ **Both `test_over_and_back.py` failures** — diagnosed as test defects (mock argument order; a self-contradictory boundary assertion). Deliberately not fixed. The second one needs a product decision on `>` vs `>=` before anyone touches it.

## Update 2026-09-06 — HCO freelance added as a consumer (Phase 3 avoidance)

The audit's scope was HCT/FCP. HCO was not on it, and HCO turned out to be the
one path that could actually put the ball behind the line: measured **4.15
ball-handler incursions and 1.65 illegal passes per game**, rendered, with
nothing detecting them. Three mechanisms, two of them data rather than logic:

| Mechanism | Kind | Fix |
|---|---|---|
| `motion_freelance.py:135` nudge — `toward` is a coin flip, clamped only to `_X_MIN/_X_MAX = 2.0/98.0` | runtime | `over_and_back.clamp_target_to_frontcourt` |
| Relocate pool iterated all 41 `HCO_STRING_SPOTS`, six of which sit behind the line | data / scoping | `HCO_OFFENSIVE_SPOTS` (positive, exhaustive membership) |
| `_resolve_collisions` offset ±2 in x with no half-court bound — and the clamp above parks players on x=50, manufacturing collisions on the line | runtime interaction | `is_away_offense` param; group is translated forward, not mirrored |

`fcp_inbound_pg` (15, 15), `fcp_inbound_sg` (11, 36) and `fcp_outlet_pf`
(43, 25) were deleted as dead data: their only consumer, the
`FCP_SETUP_POSITIONS` mapping, went away when FCP moved to
`FCP_OFFENSE_SETUP_RANGES`, leaving the freelance pool as the sole reader.

New provenance entries: `over_and_back.clamp_target_to_frontcourt` and
`motion_freelance._resolve_collisions`. **`motion_freelance.py` was added to
`_AUDITED_MODULES`** — without it the guard had a blind spot exactly where the
new logic lives, which is how the collision leak survived the first
measurement pass (it cut incursions 83 → 30, not to zero).

Avoidance-only residual, same seeds: **0 handler incursions, 0 off-ball
incursions, 0 illegal passes** over 3,176 beats / 20 games. Per the phase
constraint, no PS/CH awareness roll was added — a roll with zero opportunities
is dead code with a green test beside it.

Note the ownership blur that produced this: `HCO_STRING_SPOTS` is both the
half-court offensive vocabulary and the global named-spot registry, and
`hct_inbound_*` still live in an `HCO_*` table. Splitting the two is the real
fix; the classified sets are the guard until then.
