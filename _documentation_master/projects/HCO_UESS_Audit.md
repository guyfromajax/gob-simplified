# HCO ↔ UESS Compliance Audit

**Date:** 2026-07-04 · **Scope:** HCO turns (shared emitter path with FCP / Final Shot) · **Method:** read-only trace, 4 parallel audits (ball-seam, player-coord, single-coord-source, entry+clock) · **Result of audit only — no code changed.**

---

## ⭐ TL;DR (human topline — read this first)

**HCO's coordinate *plumbing* is solid. HCO's coordinate *authority* is not.** The step-to-step seaming (player coords + ball cursor threading) is well-built and does **not** teleport on its own. The real problems are two authority gaps that exactly match what you're feeling in the prototype:

| Your symptom | Root cause | Verdict |
|---|---|---|
| "Stale coords driving backend logic" | **HCO builds the player animation TWICE with different RNG.** The shot outcome (contest, defender pick) is decided from build #1; the frontend renders build #2. They disagree by a few grid units — enough to flip a contested shot to uncontested. | ❌ **Confirmed — HIGH** |
| "Edge-case ball teleports" | Not in HCO's own step chain (that's clean). Teleports come from **two conditional seams**: the turn boundary (ball position is re-guessed from *who* holds it, not *where* it was) and a **step-0 double-resolver bug** that can invent a phantom pass. | ⚠️ **Confirmed conditional — MED** |
| "Players in the wrong place" | The entry walk-up **only waits for the ball-handler.** The other 9 players get cut off mid-travel and then spend the whole possession chasing setup spots they may never reach. | ⚠️ **Confirmed — MED** |
| (Bonus) Game clock feels off on entries | The entry animation (handoff/kickout/walk-up) burns real seconds on screen that **never get counted** in the authoritative clock. FCP and HCT fix this; HCO forgot to. | ❌ **HIGH** |

### Compliance scorecard

| UESS contract | HCO status |
|---|---|
| Player coord step-seam continuity (§8.1) | ✅ Compliant |
| Ball coord step-seam continuity, within turn (§8.4 inv.1) | ✅ Compliant |
| Ball ownership expressed within-step (§8.4 inv.2) | ⚠️ At risk — step-0 double resolver |
| Ball turn-seam continuity (§8.4 inv.4) | ❌ Gap (known — `final_ball_coords` unbuilt) |
| Single coord source for logic (§1 / §7) | ✅ **Fixed (Task 1, 2026-07-04)** — single build; was double build |
| Clock authority = ledger, all time counted (§5) | ✅ **Fixed (Task 2, 2026-07-04)** — every HCO turn realigns from emitted steps |
| Entry orchestrator coord+ball continuity (§4) | ✅ Compliant |
| Setup-geometry fidelity (players reach authored spots) | ⚠️ At risk — BH-only gate |
| Entry possession safety | ⚠️ Latent risk — no team check |

### Fix these three, in order
1. **Stamp one animation build and reuse it** — resolve the shot from the *same* build the emitter renders (kill the RNG mismatch). This is the §7 snapshot's real payoff.
2. **Realign HCO `time_elapsed` from the emitted steps** (copy the FCP/HCT one-liner that HCO is missing).
3. **Close the two ball seams** — carry an explicit `final_ball_coords` across turns, and make step-0's start/end ball owner come from *one* resolver.

### What's genuinely fine (don't touch)
Entry handoff/kickout/walk-up coord+ball chaining · post-shot `[shoot]→[ball_flight]→[hold]/[bounce]` cursor threading · all-10-player end.coords coverage on the normal path · no mid-emit `player.coords` mutation · cold-start fallbacks · prepend chain `next`-pointer wiring.

---
---

## Full audit detail (agent-facing)

### Audit method

Four independent read-only traces against the UESS contract ([UESS_System.md](../05_UESS_System/UESS_System.md)):

1. **Ball seam continuity** — every HCO step boundary + entry + post-shot sub-steps + turn seam (§8.4).
2. **Player-coord continuity** — reseeds, mid-emit `player.coords` reads, all-10 coverage (§8.1–8.3, §9.5).
3. **Single-coord-source** — whether shot/contest/foul logic reads the emitted coords or a parallel source (§1, §7).
4. **Entry orchestrator + clock** — Handoff/Kickout/Walk-Up seams + ledger-derived `time_elapsed` (§4, §5, §11.2).

Primary files: [`skeleton_step_emitter.py`](../../BackEnd/engine/skeleton_step_emitter.py) (3150 lines), [`transition_bridge.py`](../../BackEnd/utils/transition_bridge.py), [`shot_manager.py`](../../BackEnd/models/shot_manager.py), [`phase_resolution.py`](../../BackEnd/engine/phase_resolution.py), [`turn_manager.py`](../../BackEnd/models/turn_manager.py), [`shared.py`](../../BackEnd/utils/shared.py). FE render behavior confirmed in [`animationPlayback.js`](../../FrontEnd/static/js/phaser/animation/animationPlayback.js).

---

### HIGH-1 — Double Animator build: shot outcome resolved from a different RNG draw than the frontend renders

**This is the "stale/faulty coords driving backend logic" hunch, confirmed.** It is a §1 single-coord-source violation and the flagship case §7 exists to fix.

**Order of operations (main HCO path, `resolve_half_court_offense_logic`):**

| # | Line | Action | Coord source |
|---|---|---|---|
| 1 | `phase_resolution.py:7126-7133` | **Animator build #1** → `animations` | `skeleton_to_animations` — **RNG draw A** |
| 2 | `phase_resolution.py:7232` | `apply_coords_from_animations_list` mutates every `player.coords` (incl. all 5 defenders) to build-#1 waypoints | build #1 |
| 3 | `phase_resolution.py:7233` | `set_shooter_coords_from_skeleton_last_step` sets `shooter.coords` + `roles["shot_spot"]` | `HCO_STRING_SPOTS` / explicit — **deterministic** |
| 4 | `phase_resolution.py:7235` | **`resolve_shot(roles)`** — contest from defender.coords; consumes make/miss/foul RNG | roles spot + defender.coords (build #1) |
| 5 | `turn_manager.py:3563→3591` → `skeleton_step_emitter.py:976-990` | Emitter finds no stamped `animations` (line `7283-7284` commented out) and **rebuilds them locally** | **Animator build #2 — RNG draw B** |

There is **no `random.seed`** per turn, and make/miss RNG is consumed between the builds, so **draw A ≠ draw B**. The FE renders build #2; `resolve_shot` decided from build #1.

- **Shooter position does NOT diverge** — offense spots are deterministic (`HCO_STRING_SPOTS` / explicit coords, no RNG; `animator.py:1286-1302`). 2PT/3PT classification and rim-box tests are safe.
- **Defender/contest geometry DOES diverge** — `def_lineup[...].coords` come from `get_defender_coords` jitter (`shared_defense.py:1554-1671`, ±1–5 grid/axis). `resolve_shot` reads these at `shot_manager.py:770-806`.

**Divergence is outcome-affecting on the Motion-attack path:**
```
shot_manager.py:774   dist = math.hypot(candidate_x - sx, candidate_y - sy)
shot_manager.py:775   if dist <= contest_radius:      # CONTEST_EUCLIDEAN_RADIUS = 11 (constants:307)
shot_manager.py:780   defender = contest_pairs[0][0]  # contesting defender IDENTITY, chosen by coord distance
shot_manager.py:808   has_contest = geometry_has_contest
```
Both the contested/uncontested boolean **and** the contesting-defender identity are computed from build-#1 coords. A ±1–5 jitter at radius 11 can flip a defender in/out of contest.

- **Repro (HIGH):** Motion drive shot resolves *uncontested 100%* (`shot_manager.py:890-919`) because draw-A put the guard at dist 11.4, while draw-B (rendered) puts that guard at dist 9.8 visibly contesting. Outcome contradicts the animation.
- **Standard set-play / man / zone HCO is coord-INDEPENDENT for the decision** — `has_contest = bool(defender or second_defender)` for `offensive_state=="HCO"` (`shot_manager.py:809-810`), and defender identity comes from deterministic man-matchup / zone-assignment (`_resolve_hco_shot_defenders`, `shot_manager.py:146-177`). The `geometry_has_contest` computed from build-#1 coords is **discarded** for standard HCO. So the divergence there is visual only (defenders rendered at build-#2 coords) unless a downstream reads those coords. → **MED** for standard, **HIGH** for Motion.
- `rim_unguarded_99` (`shot_manager.py:813-819`) keys off `has_contest`, inheriting HIGH on Motion.

**§7 status:** `resolve_shot(self, roles)` (`shot_manager.py:551`) takes only `roles` — no snapshot. The `position_snapshots` ledger (`build_hco_pre_resolve_shot_snapshot` → `attach_position_snapshots`, `phase_resolution.py:7234-7236`) records build-#1 coords but is **never read back** by `resolve_shot`. Confirmed not built.

**Fix direction:** stamp the build-#1 `animations` onto `shot_result` (uncomment/replace `phase_resolution.py:7283-7284`) so the emitter renders the *same* build resolve_shot used — OR resolve the shot from `shot_state_snapshot` built off the emitted steps (§7). Either collapses A and B to one draw.

**Note:** this is symmetric noise, not a directional bias, so it is unlikely to be the sole cause of the separately-tracked "FG%/3PT% too high" issue — but it makes contest outcomes non-reproducible against the render and should be fixed before further shot tuning.

---

### HIGH-2 — [CORRECTED → MED] Non-shot HCO turns approximate entry time instead of deriving it from the emitted steps

> **Correction (2026-07-04, post-verification):** The original audit claimed "HCO has no realignment, unlike FCP/HCT, and takes the `else` branch at `phase_resolution.py:1640`." **That is wrong.** The FCP/HCT realignment lives in **`turn_manager.py`**, not `phase_resolution.py`, and **HCO has the identical realignment** at [`turn_manager.py:3596-3606`](../../BackEnd/models/turn_manager.py#L3596-L3606) inside `_emit_hco_animation_steps` — it derives `time_elapsed` from the emitted `animation_steps` first/last clock, which **includes** the prepended entry-orchestrator burn. The agent conflated the resolution-dispatch `else` at `turn_manager.py:1640` with the emit path. Severity drops HIGH → **MED**.

**Real (narrowed) residual.** The emitted-steps realignment fires **only for `result_type in (MAKE, MISS, BLOCK)`** (`turn_manager.py:3596`). **Non-shot HCO turns** — TURNOVER / O_FOUL / STEAL / DEAD_BALL — instead set `time_elapsed = timing_contract["time_elapsed"]` (`phase_resolution.py:6955, 7014, …`), which is `skeleton_sum + include_hco_step1_bringup` (a lumped cruise-distance *approximation* of the bring-up, `shared.py:577-582`) — **not** derived from the emitted steps. So on a non-shot HCO turn with prepended entry steps, the clock burn the FE renders (entry + skeleton) can differ from the counted `time_elapsed` (skeleton + bring-up approximation).

- **Compliant today:** every HCO MAKE/MISS/BLOCK turn (realigned from emitted steps, entry included).
- **Non-compliant:** HCO turnover/foul/steal turns (approximation, may diverge from emitted burn).
- **Fix direction:** extend the `turn_manager.py:3596` realignment to non-shot HCO result types (or move the realignment to fire for all HCO result types) so **every** HCO turn derives `time_elapsed` from the emitted `animation_steps`, matching shot turns. Small and isolated. See Work Plan **Task 2**.

---

### MED-1 — Two divergent step-0 ball-handler resolvers can fabricate a phantom pass (teleport)

The clearest teleport candidate inside the emitter.

- **Resolver A** — `get_ball_handler_from_skeleton(step_index=0)` (`phase_resolution.py:348-395`): matches actions `{handle_ball, receive, shoot}`, iterates `pos_actions.items()` in **dict order**. Used for `step0_bh_id` (`skeleton_step_emitter.py:1094`), the delivery target for Handoff/Walk-Up.
- **Resolver B** — `_walk_ball_owners` (`skeleton_step_emitter.py:294-337`): matches `{handle_ball, pass}`, iterates `_OFFENSE_POSITIONS` (PG,SG,SF,PF,C) order. Produces per-step owners.
- The i==0 seam override sets **only the start owner**: `owner_id_start = prepended_owner` (`1495-1498`) but `owner_id_end = ball_walks[0].end_owner` (`1485-1487`) stays resolver-B-derived. If A ≠ B, `is_pass_step` (`1536-1540`, `owner_id_start != owner_id_end`) turns true and step 0 renders an **unintended pass / ownership jump across the seam**.
- **Repro:** skeleton step 0 tags the playcall BH via `receive`/`shoot` (counted by A, not B), or first `handle_ball` in dict order ≠ PG-first order → entry delivers to `step0_bh_id`, then step 0 emits a spurious pass to the ball-walk owner.
- **Fix direction:** resolve step-0 owner once; assert `step0_bh_id == ball_walks[0]` owner, or override `owner_id_end` at the seam too.

---

### MED-2 — Turn-seam ball position re-derived from owner coord, not carried (§8.4 invariant 4)

- HCO step-0 ball is `{owner_player_id: bh_id}` (every entry primitive: `transition_bridge.py:350, 652, 983`); FE resolves owner→coord from `step.start.coords` and snaps once (`animationPlayback.js:1204`) with no prior-turn reconciliation.
- `final_ball_handler_id` (`build_final_ball_handler_id`, `animation_step_helpers.py:48-97`) is resolved **separately** from `final_coords`. Nothing guarantees `final_coords[final_ball_handler_id]` equals the ball's actually-rendered rest position.
- **Repro:** prior turn ends with the ball loose / in-flight, `final_ball_handler_id` falls back through its priority chain (`ball_handler_id`, then `roles.ball_handler` → shooter, `88-97`) to a player whose synced coord ≠ the ball's rest → entry snaps ball onto that player = teleport.
- **Fix direction:** the `final_ball_coords` snapshot named in §8.4 invariant 4 — carry the explicit rendered rest position across the seam.

---

### MED-3 — Entry walk-up gates on the ball-handler only; 9 players start the possession short of authored spots

**Most likely mechanism behind "players in the wrong place."** Continuous (no teleport), technically §9.5-legal ("destinations are intent"), but it systematically diverges rendered geometry from the playcall.

- `gate_player_ids=[walk_bh_id]` (`skeleton_step_emitter.py:1296`; also fallback walk-ups `253-284`). Step T = BH travel time; all 9 others are interrupted at T (`build_walk_up_step:338-342`, `_interrupted_coord`).
- Skeleton step 0 then starts the 9 non-BH players **below** the authored `movement[0]` setup, and each subsequent skeleton step sets `destination = animator waypoint i+1` while `start = interrupted prior end`. If steps stay BH/shooter-gated, non-BH players perpetually chase spots they may never reach.
- **Repro:** any HCO entry where a non-BH player's `prior_final → setup` distance exceeds the BH's.
- **Fix direction:** tuning, not a schema bug — widen the entry gate (gate all offensive setup movers, or floor step T at the slowest setup traveler), or split entry into "walk BH" + "everyone settles" beats.

---

### MED-4 — Step-0 all-10 coverage depends on the animator at cold start

- `_coords_at_movement_index` (`skeleton_step_emitter.py:142-165`) **drops any player whose `movement[]` doesn't reach the index** (`153-154`). At i==0 with `reset_count==0` and no seed, `start_coords = _coords_at_movement_index(animations, 0)` (`1448`) — an omitted player is absent from step 0 → absent from every `end.coords` → absent from `animation_steps[-1].end.coords`.
- Downstream: `sync_lineup_coords_from_turn` seeds from current `player.coords` first (`shared.py:3508-3512`), overriding only pids present in the last step (`3546-3566`). A dropped player **keeps stale `player.coords`**, inherited into next turn's `final_coords` (§8.2 break).
- **Mitigation that usually saves HCO:** `hco_seed_coords` merges `prior_turn.final_coords` (all 10) over the animator map (`1431-1435`) — but only when `reset_count==0` AND `prior_turn` is a dict (`1364-1367`); when entry steps prepend, step 0 seeds from the entry walk-up end (all 10). **Residual exposure: HCO with `prior_turn is None`** (first offensive possession, no seed, no prepend).
- **Repro:** game-opening HCO possession where the animator emits an empty/short `movement` array for a stationary player.

---

### MED-5 — Walk-up step T floor is 0.05, not the 1.5 the UESS doc claims

**Doc/code divergence — the UESS doc is wrong here** (per convention, code wins).

- `transition_bridge.py:240` default `min_t_game_sec: float = 0.05`, applied at `326` `t = max(0.05, slowest_t)`. None of the HCO walk-up call sites pass a higher floor (`skeleton_step_emitter.py:1285-1298, 253-284`).
- [UESS_System.md §11.2](../05_UESS_System/UESS_System.md) states "Walk-up step T floor | 1.5 game-sec … T = max(1.5, slowest_gate_natural)."
- **Effect:** a short walk-up (BH already near setup) emits a sub-0.1s step that plays as a snap.
- **Action:** decide the intended floor. If 1.5 is intended, pass it at the call sites; if 0.05 is intended, correct §11.2. (See "Doc discrepancies" below.)

---

### MED-6 — Entry selection does not verify possession continuity

- `is_hco_turn` (`skeleton_step_emitter.py:1077-1082`) checks only `turn_type=="HCO"`, `prior_turn` is a dict, not `final_turn`, not `flss` — **no possession-flip / same-team check.** `current_bh_id` comes from `prior_turn.final_ball_handler_id` (`1087`) with no assertion the player is on *this* offense. `prior_final_coords` has all 10, so `has_entry_inputs` (`1108-1112`) passes even if the prior BH is an opponent → Handoff/Kickout could fire *from an opposing player*.
- Latent: made-basket/steal normally route through BIP/FCP, so it doesn't fire in practice — but nothing in the orchestrator enforces it.
- **Fix direction:** add a same-team assertion on `current_bh_id`.

---

### LOW findings

| ID | Finding | Location |
|---|---|---|
| L-1 | `reset_count==0` HCO path has no ball-owner reconciliation (no equivalent of the `1495-1498` override); ball owner from `ball_walks[0]` untied to prior handler | `skeleton_step_emitter.py:1307-1313, 1482-1487` |
| L-2 | `_resolve_turn_shooter_grid_coord` reads `player.coords` (stale prior-turn) as shot-spot fallback if all other spot sources absent (mitigated by `2589-2590` re-stamp) | `skeleton_step_emitter.py:2342, 2357-2361` |
| L-3 | Entry primitives can drive `shot_clock_remaining`/`clock_remaining` **negative** in animation (no 0-floor; game-state clock separately clamped at `turn_manager.py:5076-5077`) | `transition_bridge.py:583-586, 667-670, 1001-1004` |
| L-4 | Random entry targets (`random.uniform`) re-roll on every emit → different setup geometry if a turn is re-emitted (continuous within one emit) | `transition_bridge.py:90-106, 125-153, 179` |
| L-5 | Legacy `_apply_post_shot_overlay` hard-**snaps** rebounder/get-back/release to destination (bypasses interrupt), and that end.coords seeds next turn's `final_coords` — matches where FE renders them, so not "stale," but the one non-§9.5 seed | `skeleton_step_emitter.py:2892-2925` |
| L-6 | Regular HCO handoff pass sub-step omits `ball_motion_style="pass"` (final-turn handoff sets it at `448`) → ball tweens at default rate not canonical pass rate; in-flight state keeps it continuous (cosmetic) | `skeleton_step_emitter.py:1216-1243` |
| L-7 | Handoff HOLD variant fires when `bh==step0_bh` in backcourt — diverges from literal "no entry pass" decision-tree rule but emits no pass (compliant in spirit; documented at `1210-1215`) | `skeleton_step_emitter.py:1216` |
| INFO | `player.coords` read at `2241` is log-only (3PT SFX warning), no coordinate effect | `skeleton_step_emitter.py:2241` |

---

### Verified COMPLIANT (coverage — do not "fix")

| Boundary / contract | Evidence | Result |
|---|---|---|
| Entry substep N→N+1 (handoff, kickout) coords | `start_coords = dict(steps[-1]["end"]["coords"])` — `transition_bridge.py:517, 904` | ✅ all 10 carried |
| Entry chain last → skeleton step 0 coords | `skeleton_step_emitter.py:1416-1417` | ✅ continuous |
| Entry chain last → skeleton step 0 ball owner | `owner_id_start = _attached_owner_from_step_end(...)` — `1495-1498` | ✅ override closes seam |
| Skeleton step N→N+1 coords (i≥1) | `{**anim_start, **prior_end}`, prior end wins — `1444-1446` | ✅ §8.1 |
| Skeleton step N→N+1 ball owner | single running `current_owner` in `_walk_ball_owners` — `316-336` | ✅ internally consistent |
| Mid-skeleton pass (ownership WITHIN a step) | `is_pass_step` + `ball_arrival_coord` meet-point — `1536-1540, 1771-1797` | ✅ §8.4 inv.2 |
| `[shoot]→[ball_flight]→hops→[hold]/[bounce]` | cursor threading `cursor_ball`/`cursor_coords`/`cursor_clock` — `2748-2775, 2846-2889`; shot_spot pinned equal `2589-2590 / 2695` | ✅ ball threaded |
| all-10 `end.coords` (stationary carry) | `_build_step_end_coords_with_interrupts` iterates `start_coords.items()` — `709-747` | ✅ (except cold-start, MED-4) |
| Kickout pass shape (§4) | passer/receiver stationary, ball within-step, other 8 cruise-interrupted — `transition_bridge.py:737-756` | ✅ matches doc |
| Handoff pass shape (§4) | converge (BH holds) → within-step transfer — `608-689, 806-835` | ✅ |
| No mid-emit `player.coords` writes | grep clean across emitter + transition_bridge | ✅ §8.1 |
| Turn-end sync source | reads `animation_steps[-1].end.coords` — `shared.py:3546-3566` | ✅ §8.2 |
| Post-steal HCO transition seam | end.ball attached(stealer) becomes `final_coords` — `3138` | ✅ closes STEAL→HCO |
| Cold-start protection | missing-inputs walk-up + "never cold-start" min walk-up + loud error log — `1174-1192, 1305-1330, 1121-1166` | ✅ |
| Prepend chain `next`-pointer offset | `_wire_prepended_step_chain` + `skeleton_base_index` — `245-250, 1411` | ✅ |
| Final-turn vs generic entry | mutually exclusive (`is_hco_turn` excludes `final_turn`) — `1080, 1369-1406` | ✅ |
| OREB shot-clock reset consumed by next HCO entry | seeds `shot_clock_remaining_at_turn_start` from reset — `1017`; turn-level ledger event `turn_manager.py:402-407` | ✅ (subject to HIGH-2) |

---

### Root-cause map to reported symptoms

- **"Stale coords driving backend logic"** → **HIGH-1** (double build; defender contest geometry decided on a build the FE never shows). Not cross-turn staleness — same-turn RNG mismatch.
- **"Edge-case ball teleports"** → **MED-1** (step-0 double-resolver phantom pass) + **MED-2** (turn-seam owner-coord re-derivation) + **L-1** (`reset_count==0` no reconciliation). All conditional on prior-turn/skeleton shape → matches "intermittent."
- **"Players in the wrong place"** → **MED-3** (BH-only entry gate) + **MED-4** (cold-start animator drop).
- **Clock feels off on entries** → **HIGH-2** (entry time uncounted).

### Recommended remediation order

1. **HIGH-1** — single build (stamp+reuse `animations`, or §7 snapshot). Restores logic↔render agreement; unblocks reliable shot tuning.
2. **HIGH-2** — HCO `time_elapsed` realignment (port the FCP/HCT one-liner). Restores clock authority on entries.
3. **MED-1** — unify step-0 ball-owner resolution + assert `step0_bh_id == ball_walks[0]`. Kills the phantom-pass teleport.
4. **MED-2 / L-1** — `final_ball_coords` turn-seam carry (§8.4 inv.4 build target). Kills the turn-seam teleport.
5. **MED-3** — entry-gate breadth (tuning). Fixes setup-geometry fidelity.
6. **MED-6, MED-4, L-*** — hardening.

### Doc discrepancies found (in UESS_System.md, to reconcile separately)
- **§11.2 walk-up floor**: doc says **1.5 game-sec**, code default is **0.05** (`transition_bridge.py:240`). One is wrong — see MED-5.

### Appendix — key line index
- Double build: `phase_resolution.py:7126-7133, 7232-7236, 7283-7287, 1640`; `skeleton_step_emitter.py:976-990`; `shot_manager.py:551, 767-819, 146-177`; `shared_defense.py:1554-1671`; `constants:307`.
- Clock: `turn_manager.py:257-272, 295-296, 5072-5077`; `shared.py:440, 577-582`; `phase_resolution.py:1592-1594, 1633-1640`.
- Ball seams: `skeleton_step_emitter.py:294-337, 1094, 1416-1417, 1485-1498, 1536-1540, 1690-1692`; `animation_step_helpers.py:48-97`; `phase_resolution.py:348-395`.
- Player coords: `skeleton_step_emitter.py:142-165, 709-747, 1296, 1364-1367, 1431-1448, 2342, 2892-2925`; `shared.py:3508-3512, 3546-3566`; `transition_bridge.py:224-342`.

---
---

## Work Plan — HCO → 100% UESS alignment

Four tasks, implemented **one at a time with verification between each** (this is the game's most core execution path). Tasks 1 & 3 both touch the emitter's step-0 region → do **1 before 3**. Task 2 is isolated; Task 4 is narrowest.

**Strict-compliance set:** Tasks 1–4 (all fix real contract violations). **Quality add-ons (optional, not contract violations):** MED-3 entry-gate breadth, MED-6 possession check, LOW-* — tracked but not in this plan unless you want them.

Order: **1 → 2 → 3 → 4.**

---

### Task 1 — Single animation build (fixes HIGH-1, §1/§7) — ✅ DONE & VERIFIED (2026-07-04)

**Status:** Shipped (Option A). `resolve_half_court_offense_logic` ([`phase_resolution.py:7123-7251`](../../BackEnd/engine/phase_resolution.py#L7123)) now defers the animator build until the skeleton is finalized, builds once, and stamps `shot_result["animations"]`; the emitter reuses it instead of rebuilding.
**Verification (mongomock spy, 10 HCO shot turns):** animator builds per shot turn dropped **2 → 1** (pre-fix sites `7128` + emitter `983`; post-fix site `7234` only). Stamp fired 10/10, `animation_steps` emitted 10/10. Regression: 27 UESS clock/ownership/turn/serialization tests pass; the 4 failures observed are pre-existing (confirmed by git-stash isolation), unrelated to this change. Expected gameplay consequence (accepted): Motion shot outcomes now resolve from the finalized/rendered geometry → FG%/3PT% will shift; re-tune shooting *after* all four tasks land.

**Goal:** HCO shot resolution and the emitted animation use **one** animator build — same RNG draw *and* same (finalized) skeleton — so the coords that decide the outcome are the coords the FE renders.

**Design decision (resolve before coding):**
- **Option A — build-once-and-stamp (RECOMMENDED).** Build the animator **after** the skeleton is finalized, stamp `turn_result["animations"]`, and let both `resolve_shot` and the emitter consume it. Surgical; the emitter already reuses `turn_result["animations"]` if present (`skeleton_step_emitter.py:965, 976`).
- **Option B — §7 snapshot.** Emit steps first, build `shot_state_snapshot` from the emitted `end.coords`, resolve the shot from the snapshot. Truer to §7 but inverts resolve/emit order — larger blast radius. Defer to the standalone §7 build.

**Implementation steps (Option A):**
1. In `resolve_half_court_offense_logic` (`phase_resolution.py`), move the single animator build to **after** the skeleton is finalized — i.e. after the Motion/set-play skeleton modifications (`~7179-7204`), not at the current `7128` (which builds from the *original* skeleton, before Motion edits it).
2. Stamp `turn_result["animations"] = animations` (the finalized build) so the emitter's guard at `skeleton_step_emitter.py:976` (`if not animations…`) is skipped and it renders the exact build resolve_shot used.
3. Keep `apply_coords_from_animations_list(game, animations)` (`7232`) + `resolve_shot` (`7235`) reading that same build.
4. **Match build parameters.** The emitter's internal build passes `add_defenders=True, is_fcp=(turn_type=="FCP"), is_hct=False` (`983-990`); the phase build passes `add_defenders=True` (`7128`). Confirm the stamped build is parameter-equivalent to what the emitter would have built (esp. `is_fcp`/`is_hct` for the shared FCP path — FCP already stamps differently, so scope this change to HCO).
5. **Motion/set-play paths:** verify the finalized-skeleton build feeds correct coords to `apply_coords`/`resolve_shot` (the modified skeleton is the real one). Ensure early-return paths (pass interception `7173-7175`) are unaffected.
6. Leave the `position_snapshots` audit ledger as-is (it now records the single build — becomes a true forensic mirror).

**Verification:** play an HCO Motion drive; confirm the defender coords `resolve_shot` reads == the emitted shot-step `end.coords` for those defenders (temp-log both, or diff `position_snapshot` vs emitted step). Contest outcome must match what's rendered. Run a set-play shot + a turnover to confirm no regression.

**Risk:** RNG parameter drift between the two former call sites; FCP shares this emitter (scope the stamp to HCO only).

---

### Task 2 — All HCO turns derive `time_elapsed` from the emitted steps (fixes corrected HIGH-2, §5) — ✅ DONE & VERIFIED (2026-07-04)

**Status:** Shipped. `_emit_hco_animation_steps` ([`turn_manager.py:3595-3606`](../../BackEnd/models/turn_manager.py#L3595)) realignment gate widened from `result_type in (MAKE,MISS,BLOCK)` to `if anim_steps:` — every HCO turn now derives `time_elapsed` from the emitted first/last-step clock. Final Shot / FLSS overrides preserved; Force Foul does not reach this emitter (handled at DREB time in game_manager); no non-shot override existed to clobber (turnover/foul only set `= timing_contract`).
**Verification (mongomock, 8 non-shot HCO turns — FOUL/DEAD_BALL):** post-fix `time_elapsed == emitted burn` 8/8. Pre-fix (same seed) diverged **8/8**, by up to ~2.4× (e.g. FOUL counted 12 vs rendered 5; DEAD_BALL 6 vs 3) — the counted clock over-burned vs the animation. Regression: 30 clock/ownership tests pass; the 1 failure (`test_make_shot_family…`) is a synthetic-result MAKE test that never routes through this emitter and fails on clean code (pre-existing, from other uncommitted tree changes). **Gameplay consequence (accepted):** game-clock now burns *less* on non-shot HCO turns (matches render) → slightly more possessions/quarter; watch pace + FGA alongside Task 1's FG% shift.

**Goal:** every HCO turn — shot **and** non-shot — derives `time_elapsed` from the emitted `animation_steps`, so entry-orchestrator time is always counted (today only MAKE/MISS/BLOCK are).

**Implementation steps:**
1. In `_emit_hco_animation_steps` (`turn_manager.py:3595-3606`), extend the realignment condition beyond `("MAKE","MISS","BLOCK")` to also cover non-shot HCO result types (TURNOVER / O_FOUL / STEAL / DEAD_BALL) — or unconditionally realign for HCO, with explicit exclusions.
2. **Preserve the intentional exceptions:** Final Shot / FLSS already force `time_elapsed = time_remaining` / `max(1, te)` (`3604-3614`) — keep those guards. Do not touch the OREB path (separate, §5.4).
3. Confirm non-shot downstream consumers of `timing_contract` fields (`step_clock_seconds`, `bringup_per_player_seconds`, shot-clock accounting) still receive what they need — realign only `time_elapsed`, leave the other stamped fields intact.

**Verification:** HCO turnover (and an O_FOUL) with a Kickout/Handoff entry prepended; assert `time_elapsed == round(anim_steps[0].start.clock.clock_remaining − anim_steps[-1].end.clock.clock_remaining)`. Compare to pre-change value to quantify the drift being fixed.

**Risk:** low — mirrors an already-proven realignment; main care is not clobbering Final Shot/FLSS.

---

### Task 3 — Close the two ball seams (fixes MED-1 + MED-2, §8.4 inv.2 & inv.4)

Two independent sub-parts; ship together or as 3a then 3b.

**3a — Unify step-0 ball-owner resolution (MED-1, phantom-pass teleport):**
1. Reconcile the two resolvers: `get_ball_handler_from_skeleton` (actions `{handle_ball,receive,shoot}`, dict order; `phase_resolution.py:348-395`) vs `_walk_ball_owners` (actions `{handle_ball,pass}`, PG-first; `skeleton_step_emitter.py:294-337`). Pick one action-set + ordering as canonical for step 0.
2. At the i==0 seam override (`skeleton_step_emitter.py:1495-1498`), reconcile `owner_id_end` too — today only `owner_id_start` is overridden, so `is_pass_step` (`1536-1540`) can turn true when the resolvers disagree.
3. Add a temporary assert/log `step0_bh_id == ball_walks[0].end_owner` to catch disagreement in the wild; remove once clean.

**3b — Carry `final_ball_coords` across the turn seam (MED-2, §8.4 inv.4 build target):**
1. Add `build_final_ball_coords(turn_result)` in `animation_step_helpers.py` — resolve the ball's rest position from `animation_steps[-1].end.ball` (attached→owner coord; loose/in-flight→explicit coord).
2. Stamp `turn_result["final_ball_coords"]` in `_append_turn` (`game_manager.py`), alongside `final_coords` / `final_ball_handler_id`.
3. In the HCO entry orchestrator, seed step-0 ball **position** from `prior_turn.final_ball_coords` when present; if the step-0 owner's coord differs from the carried ball position, express the reconciliation as a **within-step** move (loose→attached), never a seam snap.
4. Update UESS_System.md §8.4 invariant 4 to mark `final_ball_coords` **built**.

**Verification:** chain a turn that ends ball-loose or in-flight (e.g. missed-shot → DREB → HCO) into an HCO possession; assert step-0 resolved ball position == prior `final_ball_coords` (no snap). Watch the render for a teleport at the seam. For 3a: force a skeleton whose step-0 tags the BH via `receive`/`shoot` and confirm no phantom pass emits.

**Risk:** 3b interacts with the FE's unconditional turn-entry snap (`animationPlayback.js:1204`) — the carry must make step-0 start == prior end so the snap is a no-op; verify visually.

---

### Task 4 — Cold-start step-0 coord coverage (fixes MED-4, §8.2)

**Goal:** step 0 always covers all 10 players, even when `prior_turn is None` and the animator omits a player from `movement[0]`, so no player carries stale `player.coords` across the seam.

**Implementation steps:**
1. Make `_coords_at_movement_index` (`skeleton_step_emitter.py:142-165`) **carry forward** the last known coord for a player whose `movement[]` is shorter than the index, instead of dropping them (`153-154`) — OR
2. At cold start (`reset_count==0` and `prior_turn is None`, the residual exposure), seed step-0 `start_coords` for any missing player from the live lineup coords so all 10 are present before the loop.
3. Confirm coverage propagates (the end-coords builder already iterates `start_coords.items()`, `709-747`, so fixing start fixes end).

**Verification:** game-opening HCO possession with a stationary player omitted from `movement[0]`; assert all 10 present in `animation_steps[-1].end.coords` and that the player's next-turn `final_coords` is not stale.

**Risk:** choosing the fallback source — must be the player's actual current position, not a default, to avoid introducing the very teleport we're removing.

---

### Cross-task verification (after all four)
Full HCO possession sweep — Motion make, Motion miss→OREB, set-play make, turnover, foul, steal→HCO, first-possession HCO — checking: (a) contest outcome matches render (T1), (b) game/shot clock matches emitted burn on every result type (T2), (c) no ball teleport at any step or turn seam (T3), (d) all 10 players positioned every step (T4). Then re-run this audit's four traces to confirm each dimension flips to ✅.
