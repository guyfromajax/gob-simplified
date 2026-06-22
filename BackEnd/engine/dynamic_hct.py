"""
Dynamic HCT (Half Court Trap) turn resolution.

Spec: ``_documentation_master/projects/Dynamic_HCT_Turns.md`` (single source of
truth — the former Cut2 build-plan and D8 scoping docs are merged into it).

Cut 2 / Phase 2A scope — the §4 loop spine:
  - Setup (segment 0): entry walk-up. BH advances from BIP receive coords to
    ``(44, target_y)`` (``target_y`` random in [21, 29]); the 9 others move
    toward their targets. Built by the emitter via the universal walk-up step.
  - Internal loop (variable-length): the engine returns ``loop_segments`` —
    a converge segment (defensive PG slides onto the BH) followed by one
    segment per iteration:
      * Time terminals (shot-clock ≤ 0, or 10-sec while still in backcourt)
        end the possession as a turnover.
      * Zone precedence: BH in the Primary Safe Area (or past it) → HCO.
      * Read (attack / pass / hold). Phase 2A fully resolves **attack** via
        the §5 banded contested formula → DEAD BALL / POS_O / NEUTRAL.
        POS_O and NEUTRAL advance; **pass / hold are placeholder-routed to
        neutral-advance** until Phase 2B/2C.
      * Advance: BH dribbles +rand(6,12) x toward basket, +rand(-6,6) y; the
        PG defender re-poses to stay engaged.
    Every target passes through the universal animation clamp.

The engine returns intermediate data only (targets, per-segment durations,
result type); ``dynamic_hct_step_emitter.build_dynamic_hct_animation_steps``
turns it into the walk-up step + one schema step per segment.

Moment system (pressure vs. trap) and the pass branch landed in Phases 2B–2C.
Phase 2D-1 added the broken-HCT **fast break (D18)**: when the open-floor attack
reaches the topLane spot (perfect-PSA spot behind the BH), the engine emits
``result_type = "FAST_BREAK_SHOT"`` + a ``fb_seed``; the wrapper hands off to
``dynamic_hct_shot.resolve_hct_fast_break_shot`` for a real make/miss rim attempt.
Phase 2D-2a added the §7 in-Attack-Basket shot: when the BH reaches the Attack
Basket Area (x>64, y 10-30) and a goal-achievement read favours a shot, the
engine emits a shot result + an ``ab_seed`` and the wrapper hands off to
``dynamic_hct_shot``: ``ATTACK_BASKET_SHOT`` → shoot-in-place (2D-2a), or
``ATTACK_BASKET_DRIVE`` → drive / 50-50 drive→dish (2D-2b), both via D5 rim
collapse + D6 shot-defender + a rolled make/miss. The §7 shoot/drive/pass read
(`_choose_shot_attempt`) picks the leaf; the **pass** leaf (2D-2c) emits a real
top-level pass (`_select_top_level_pass_receiver`) and resolves the receiver's
catch — attack via the D18 bridge / Kick-Out→HCO inside the Attack Basket Area,
or loop re-entry past x=64 off-band. Fouls/steals and remaining stat parity
arrive next.
"""
from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    STANDARD_GRID_PER_GAME_SEC,
    HCO_STRING_SPOTS,
    HCT_SETUP_POSITIONS,
    RESET_INBOUND_PASS_GRID_PER_GAME_SECOND,
    HOME_RIM_COORDS,
    AWAY_RIM_COORDS,
    HCT_DRIFT_PROBABILITY,
)
from BackEnd.utils.shared import (
    ag_to_grid_per_game_sec,
    calc_ag_segment_seconds,
    calculate_ball_handling_score,
    calculate_defender_pressure_score,
    clamp_animation_grid_coords,
    get_away_player_coords,
)
from BackEnd.engine.cutoff_resolution import best_cutoff_on_drive, resolve_cutoff_contest
from BackEnd.constants.hct_trap_play_types import STANDARD_DIAMOND
from BackEnd.utils.shared_defense import HCT_STANDARD_NORMAL, compute_hct_trap_formation
from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec, drift_or_hold_coord
from BackEnd.utils.transition_bridge import _interrupted_coord
from BackEnd.engine.pass_contest import (
    BAT_OOB,
    INTERCEPT,
    resolve_offense_pass_modifier,
    resolve_pass_contest,
)


# 10-second violation gate (per Dynamic_HCT_Turns.md "Special Situations").
# 10-second backcourt rule: if this many ACTUAL game-seconds elapse from the start
# of the possession without the ball handler crossing half court, we announce a
# "10-Second Violation" and run the standard dead-ball-turnover flow → SIP. Measured
# as elapsed time (start shot clock − current), NOT an absolute shot-clock value, so
# it stays correct when the shot clock is capped to a short quarter. It also cannot
# fire if fewer than this many seconds remained in the quarter at possession start
# (the period buzzer ends the possession first).
HCT_TEN_SECOND_LIMIT = 10.0

# FCP: BIP inbound baseline x (home orientation). SF at this spot is ineligible
# as a pass target until he clears the inbound spot (Dynamic_FCP_Brief §1.1).
FCP_INBOUND_BASELINE_X_HOME = 3

# Step 1 BH target: x = 44, y random in [21, 29].
STEP_1_BH_TARGET_X = 44
STEP_1_BH_TARGET_Y_MIN = 21
STEP_1_BH_TARGET_Y_MAX = 29

# Step 2 defensive PG converge offset: defender x = BH_x + 2 (toward home basket
# in home-defending orientation), same y as BH.
STEP_2_DEFENDER_X_OFFSET = 2

# FCP engagement: the closing party lands this many grid spots from the anchor
# (the other player's setup spot) on the approach side.
FCP_ENGAGEMENT_X_SPACING = 2

# Step 3 HCO transition target: BH dribbles to deep key spot.
DEEP_KEY_SPOT = HCO_STRING_SPOTS["deep key"]  # (57, 25)

# Defensive PG's step-1 target (override per spec): exact center court spot.
DEFENSIVE_PG_STEP_1_TARGET = HCO_STRING_SPOTS["center court"]  # (50, 25)

# Pos1-4 geometric ranges (home-on-offense orientation; flipped at runtime when
# away is on offense). Each range is (x_min, x_max, y_min, y_max).
POS_TARGET_RANGES = {
    "pos1": (51, 57, 35, 45),  # upper outlet: just past half court → deep upper wing
    "pos2": (51, 57, 5, 15),   # lower outlet: just past half court → deep lower wing
    "pos3": (73, 80, 7, 19),   # lower apex / midPost region
    "pos4": (73, 80, 32, 43),  # upper apex / midPost region
}

# --- Cut 2 / Phase 2A loop parameters (home-on-offense orientation) ---------
POSITIONS = ("PG", "SG", "SF", "PF", "C")

# Primary Safe Area (§2): x 57-64. D21: a *target area only* — no longer a
# trap-break trigger. ``PSA_X_MAX`` (64) still gates the "past the PSA band"
# check that fronts the Attack Basket Area. (The y-band / perfect-spot are
# retained for reference only.)
PSA_X_MIN, PSA_X_MAX = 57, 64
PSA_Y_MIN, PSA_Y_MAX = 19, 32
PSA_PERFECT_SPOT = {"x": 60, "y": 25}

# §5 broken-HCT cutoff target: the open-floor attack drives (vs the closest
# defender, D21) to a spot inside the Attack Basket Area keyed to the BH's y:
#   19 ≤ y ≤ 32 → topLane; y > 32 → upper apex; y < 19 → lower apex.
# Reaching it clean → §7 FB/HCO.
TOPLANE_SPOT = HCO_STRING_SPOTS["topLane"]      # (74, 25)
UPPER_APEX_SPOT = HCO_STRING_SPOTS["upper apex"]  # (80, 36)
LOWER_APEX_SPOT = HCO_STRING_SPOTS["lower apex"]  # (80, 15)
BROKEN_HCT_DRIVE_Y_MIN = 19  # below → lower apex
BROKEN_HCT_DRIVE_Y_MAX = 32  # above → upper apex; within [min, max] → topLane

# §7 Attack Basket Area (§2): x 64→basket, y 10-40 (the band spans lower wing y
# → upper wing y; corrected from the earlier erroneous 10-30, D22). The sole
# trap-break zone (D21) — the BH attempts a shot / FB or transitions to HCO when
# he reaches it. Effectively x>64 (the x=64 boundary belongs to the PSA band).
ATTACK_BASKET_Y_MIN, ATTACK_BASKET_Y_MAX = 10, 40

# §7 goal-achievement read (§2 3-tier HCO/FB): read > HIGH → optimal choice;
# MID < read ≤ HIGH → HCO unless the offense is set "aggressive" (then FB);
# read ≤ MID → 50/50 random.
GOAL_ACHIEVEMENT_READ_THRESHOLD = 200
ABA_READ_MID_THRESHOLD = 125

# §7 shot-attempt optimal tree: SH > this → shoot; elif SC+AG > this → drive; else pass.
SHOOT_SH_THRESHOLD = 80
DRIVE_SCAG_THRESHOLD = 105

# §7 top-level pass: open-rim override radius (euclidean grid spots).
TOP_PASS_OPEN_RIM_RADIUS = 9

# §7 / D5 rim-protection cluster the defenders collapse into on a shot attempt
# (x from midLane−3 toward the basket, y within ±6 of basket-y). The resolver
# (`dynamic_hct_shot`) owns the actual collapse + shot-defender (D6) geometry.
RIM_PROTECT_X_MIN, RIM_PROTECT_X_MAX = 77, 87
RIM_PROTECT_Y_MIN, RIM_PROTECT_Y_MAX = 19, 31

# §4 read thresholds (attack / pass; else low-tier roll).
READ_ATTACK_THRESHOLD = 200
READ_PASS_THRESHOLD = 120

# §5 broken-HCT (no defender in range) reduced read thresholds.
BROKEN_READ_ATTACK_THRESHOLD = 175
BROKEN_READ_PASS_THRESHOLD = 110

# §4 dynamic read mapping: a "strong handler" (BH + AG above this sum) drives on
# a high read and passes on a mid read; a "weak handler" is INVERTED — a high
# read kicks it out (pass) and a mid read forces a drive (attack).
READ_STRONG_HANDLER_SUM = 80
# §4 low tier (read below the pass threshold): no longer a hard hold — roll this
# pool (50% hold, 25% attack, 25% pass).
READ_LOW_TIER_CHOICES = ("hold", "hold", "attack", "pass")

# §4 neutral-advance: BH moves +rand(ADV_X) toward basket, +rand(ADV_Y) in y.
ADVANCE_X_MIN, ADVANCE_X_MAX = 6, 12
ADVANCE_Y_MIN, ADVANCE_Y_MAX = -6, 6

# §5 moment detection: a defender is "in range" within this euclidean distance.
MOMENT_RANGE = 11

# §6 shift triggers (on ball-handler y): y < 20 → lower; y > 30 → upper; else normal.
SHIFT_LOWER_Y = 20
SHIFT_UPPER_Y = 30

# §5 hold resolution: BH holds the ball for random(1, 2) game seconds.
HOLD_SECONDS_MIN, HOLD_SECONDS_MAX = 1, 2

# §6 pass flight speed (grid spots / game-second). Reuses the universal pass
# primitive's reset-inbound rate so HCT pass timing matches other pass steps.
PASS_GRID_PER_GAME_SEC = float(RESET_INBOUND_PASS_GRID_PER_GAME_SECOND)

# Defensive backstop only — the shot-clock terminal is the real loop bound.
MAX_LOOP_ITERATIONS = 15

# --- D8: attribute-driven foul / steal / turnover moment outcomes -----------
# See _documentation_master/projects/Dynamic_HCT_Turns.md §5 (Attribute-driven
# contest model). One tunable
# block so balancing is a single-file edit. Team attrs (discipline / pt_eff /
# pt_opp / fight) are centered at 0 (±10); player attrs are ~0-100.
#
# Even-matchup baseline split among defense-wins events (→ 50% / 30% / 20%).
HCT_D8_DB_W0 = 50.0
HCT_D8_STEAL_W0 = 30.0
HCT_D8_OFOUL_W0 = 20.0
# Game-plan aggression dial → steal weight + event-fire rate + D_FOUL prob.
HCT_D8_AGG_MULT = {"passive": 0.7, "normal": 1.0, "aggressive": 1.3}
HCT_D8_GLOBAL_SCALAR = 1.0        # master per-moment event-frequency knob
HCT_D8_DEF_WIN_BASE = 0.45        # base P(any event) when defense fully wins
HCT_D8_P_EVENT_MAX = 0.60         # cap on per-moment event prob
HCT_D8_M_REF = 25.0               # margin that counts as a "decisive" win
HCT_D8_REF = 50.0                 # league-average attribute (centering)
HCT_D8_F_MIN, HCT_D8_F_MAX = 0.3, 2.5   # clamp on each attribute factor
HCT_D8_S_SENS = 1.2               # steal sensitivity to (defender − BH) gap
HCT_D8_DB_SENS = 1.0              # dead-ball sensitivity to weak BH handle
HCT_D8_O_SENS_IQ = 0.8            # charge sensitivity to (defender IQ − BH IQ)
HCT_D8_O_SENS_DISC = 0.5          # charge sensitivity to team discipline
HCT_D8_DISC_SCALE = 20.0          # discipline normalizer (team attrs ≈ ±10)
HCT_D8_W_PTEFF = 0.04             # def pt_efficiency → steal factor
HCT_D8_W_PTOPP = 0.04             # off pt_opp_modifier → resist self-TO
HCT_D8_W_FIGHT = 0.04             # OFFENSE fight → fewer D-wins events (= W_DISC_REACH)
HCT_D8_DFOUL_BASE = 0.12          # base P(D_FOUL) on a decisive blow-by
HCT_D8_P_DFOUL_MAX = 0.25         # cap on D_FOUL prob
HCT_D8_W_DISC_REACH = 0.04        # team discipline → fewer reach fouls
HCT_D8_W_AG_BEATEN = 0.6          # defender AG deficit vs BH → reach foul

# §5 D_FOUL fouler spread: the on-ball defender's blow-by is the root cause, but
# the foul itself sometimes lands on a teammate forced into an off-ball
# compensating foul. The on-ball case is the only true "Reaching In".
HCT_DFOUL_PRIMARY_P = 0.60        # on-ball (BH) defender → reach-in
HCT_DFOUL_BACKCOURT_P = 0.30      # another backcourt defender (PG/SG/SF, incl. trapper)
# remaining 0.10 → a frontcourt defender (PF/C); empty pools fall back to on-ball.
HCT_BACKCOURT_POS = ("PG", "SG", "SF")
HCT_FRONTCOURT_POS = ("PF", "C")


def _clampf(value: float, lo: float, hi: float) -> float:
    """Clamp a float to [lo, hi]."""
    return max(lo, min(hi, value))


def _team_aggression_call(team) -> str:
    """Resolved per-turn aggression call ∈ {passive, normal, aggressive}."""
    calls = getattr(team, "strategy_calls", {}) or {}
    call = calls.get("aggression_call", "normal")
    return call if call in HCT_D8_AGG_MULT else "normal"


def _aggression_call(def_team) -> str:
    """Resolved per-turn defensive aggression call ∈ {passive, normal, aggressive}."""
    return _team_aggression_call(def_team)


def _fcp_approach_x(from_x: int, anchor_x: int, spacing: int = FCP_ENGAGEMENT_X_SPACING) -> int:
    """Target x ``spacing`` grid spots from ``anchor_x`` on the approach side of ``from_x``."""
    if from_x < anchor_x:
        return anchor_x - spacing
    if from_x > anchor_x:
        return anchor_x + spacing
    return from_x


def _fcp_engagement_ends(
    bh_xy: Dict[str, Any],
    def_pg_xy: Dict[str, Any],
    off_agg: str,
    def_agg: str,
) -> Tuple[Dict[str, int], Dict[str, int], Tuple[str, str], str]:
    """FCP aggression engagement targets from BIP setup spots (pure).

    Returns ``(bh_end, def_pg_end, gate, label)``. Each side holds when it is
    not the closing party. Equal aggression → both meet at the x midpoint at the
    BH's setup y.
    """
    bh = {"x": int(bh_xy["x"]), "y": int(bh_xy["y"])}
    dpg = {"x": int(def_pg_xy["x"]), "y": int(def_pg_xy["y"])}

    if off_agg == "aggressive" and def_agg != "aggressive":
        bh["x"] = _fcp_approach_x(bh["x"], dpg["x"])
        bh["y"] = dpg["y"]
        return _clamp_xy(bh), dpg, ("off", "PG"), "fcp engagement (offense closes on press)"

    if off_agg == "normal" and def_agg == "passive":
        bh["x"] = _fcp_approach_x(bh["x"], dpg["x"])
        bh["y"] = dpg["y"]
        return _clamp_xy(bh), dpg, ("off", "PG"), "fcp engagement (offense closes on press)"

    if def_agg == "aggressive" and off_agg != "aggressive":
        dpg["x"] = _fcp_approach_x(dpg["x"], bh["x"])
        dpg["y"] = bh["y"]
        return bh, _clamp_xy(dpg), ("def", "PG"), "fcp engagement (defense closes on ball)"

    if def_agg == "normal" and off_agg == "passive":
        dpg["x"] = _fcp_approach_x(dpg["x"], bh["x"])
        dpg["y"] = bh["y"]
        return bh, _clamp_xy(dpg), ("def", "PG"), "fcp engagement (defense closes on ball)"

    meet = _clamp_xy(
        {"x": int(round((bh["x"] + dpg["x"]) / 2)), "y": bh["y"]}
    )
    return meet, meet, ("off", "PG"), "fcp engagement (meet at midpoint)"


def _apply_fcp_engagement(
    off_coords: Dict[str, Dict[str, int]],
    def_coords: Dict[str, Dict[str, int]],
    bh_pos: str,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    off_team: Any,
    def_team: Any,
) -> Tuple[float, Tuple[str, str], str]:
    """Mutate BH + def PG for the FCP aggression engagement beat; return timing."""
    off_agg = _team_aggression_call(off_team)
    def_agg = _team_aggression_call(def_team)
    bh_start = dict(off_coords[bh_pos])
    def_pg_start = dict(def_coords["PG"])
    bh_end, def_pg_end, gate, label = _fcp_engagement_ends(
        bh_start, def_pg_start, off_agg, def_agg,
    )

    bh_player = off_lineup.get(bh_pos)
    pg_def = def_lineup.get("PG")
    seconds_list: List[float] = []
    if bh_end["x"] != bh_start["x"] or bh_end["y"] != bh_start["y"]:
        seconds_list.append(
            calc_ag_segment_seconds(bh_start, bh_end, bh_player, archetype="standard")
        )
    if def_pg_end["x"] != def_pg_start["x"] or def_pg_end["y"] != def_pg_start["y"]:
        seconds_list.append(
            calc_ag_segment_seconds(def_pg_start, def_pg_end, pg_def, archetype="standard")
        )
    seconds = max(0.4, max(seconds_list) if seconds_list else 0.4)

    if bh_end["x"] != bh_start["x"] or bh_end["y"] != bh_start["y"]:
        bh_rate = _ag_grid_per_game_sec(bh_player, "standard")
        off_coords[bh_pos] = _clamp_xy(
            _interrupted_coord(bh_start, bh_end, bh_rate, seconds)
        )
    if def_pg_end["x"] != def_pg_start["x"] or def_pg_end["y"] != def_pg_start["y"]:
        pg_rate = _ag_grid_per_game_sec(pg_def, "standard")
        def_coords["PG"] = _clamp_xy(
            _interrupted_coord(def_pg_start, def_pg_end, pg_rate, seconds)
        )

    # Gate side uses the ball-handler position key, not a hardcoded "PG".
    gate_side, gate_pos = gate
    if gate_side == "off":
        gate = (gate_side, bh_pos)
    return seconds, gate, label


def _flip(coords: Dict[str, Any]) -> Dict[str, Any]:
    """Flip a coord dict around x=50 (no-op for y)."""
    return get_away_player_coords({"x": int(coords["x"]), "y": int(coords["y"])})


def _zone_centroid(spot_names: List[str]) -> Dict[str, int]:
    """Average (x, y) for a list of HCO spot names."""
    xs = []
    ys = []
    for name in spot_names:
        spot = HCO_STRING_SPOTS.get(name)
        if not spot:
            continue
        xs.append(spot["x"])
        ys.append(spot["y"])
    if not xs:
        return {"x": 50, "y": 25}
    return {"x": int(round(sum(xs) / len(xs))), "y": int(round(sum(ys) / len(ys)))}


def _alias_map(ball_handler_pos: str) -> Dict[str, str]:
    """
    Map ``pos1..pos4`` → actual position keys (PG/SG/SF/PF/C), excluding the BH
    position. Mirrors ``_build_set_play_alias_map`` in playbook_weights_utils.
    """
    order = ["PG", "SG", "SF", "PF", "C"]
    bh = ball_handler_pos.upper()
    remaining = [p for p in order if p != bh]
    return {f"pos{i + 1}": pos for i, pos in enumerate(remaining)}


def _euclid(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def _interpolate(start: Dict[str, Any], end: Dict[str, Any], progress: float) -> Dict[str, int]:
    """Linear interpolation; ``progress`` clamped to [0, 1]."""
    p = max(0.0, min(1.0, progress))
    return {
        "x": int(round(start["x"] + (end["x"] - start["x"]) * p)),
        "y": int(round(start["y"] + (end["y"] - start["y"]) * p)),
    }


def _move_at_pace(
    start: Dict[str, Any],
    target: Dict[str, Any],
    elapsed_game_sec: float,
    rate_units_per_sec: float,
) -> Dict[str, int]:
    """
    Where is a mover at ``elapsed_game_sec`` game-seconds in, given they walk in
    a straight line from ``start`` toward ``target`` at ``rate_units_per_sec``?
    """
    distance = _euclid(start, target)
    if distance <= 0 or elapsed_game_sec <= 0:
        return {"x": int(start["x"]), "y": int(start["y"])}
    travel = rate_units_per_sec * elapsed_game_sec
    if travel >= distance:
        return {"x": int(target["x"]), "y": int(target["y"])}
    return _interpolate(start, target, travel / distance)


def _pos_target(pos_key: str, is_away_offense: bool) -> Dict[str, int]:
    """
    Random target for a non-BH offensive teammate inside the geometric range
    for ``pos_key`` ("pos1".."pos4"). Flipped when away is on offense.
    """
    x_min, x_max, y_min, y_max = POS_TARGET_RANGES[pos_key]
    target = {
        "x": random.randint(x_min, x_max),
        "y": random.randint(y_min, y_max),
    }
    if is_away_offense:
        return _flip(target)
    return target


def hct_initial_defender_coords(is_away_offense: bool) -> Dict[str, Dict[str, int]]:
    """Defensive alignment at the start of an HCT possession — also the
    coords BIP plants defenders at on a HCT-next inbound. PG sits at center
    court; the other four occupy the centroid of their HCT_STANDARD_NORMAL
    polygon. Stored in home-defending orientation; flipped for away offense.

    Shared by ``setup_baseline_inbound`` (so BIP-end matches HCT step 0
    movement[0]) and ``compute_dynamic_hct_turn`` (so the start of step 1
    no longer reads stale ``player.coords``).
    """
    out: Dict[str, Dict[str, int]] = {}
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if pos == "PG":
            coord = dict(DEFENSIVE_PG_STEP_1_TARGET)
        else:
            coord = _zone_centroid(HCT_STANDARD_NORMAL.get(pos) or [])
        if is_away_offense:
            coord = _flip(coord)
        out[pos] = coord
    return out


def _build_step_1_targets(
    ball_handler_pos: str,
    is_away_offense: bool,
) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
    """
    Produce ``(off_targets, def_targets)`` dicts mapping position → target
    coords (in current orientation) for step 1.
    """
    bh = ball_handler_pos.upper()

    # BH target: (44, random y in 21-29).
    bh_target = {
        "x": STEP_1_BH_TARGET_X,
        "y": random.randint(STEP_1_BH_TARGET_Y_MIN, STEP_1_BH_TARGET_Y_MAX),
    }
    if is_away_offense:
        bh_target = _flip(bh_target)

    off_targets: Dict[str, Dict[str, int]] = {bh: bh_target}
    alias = _alias_map(bh)
    for alias_key, real_pos in alias.items():
        off_targets[real_pos] = _pos_target(alias_key, is_away_offense)

    # Defensive targets: PG → exact center court; others → zone-Normal centroid.
    def_targets: Dict[str, Dict[str, int]] = {}
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if pos == "PG":
            target = dict(DEFENSIVE_PG_STEP_1_TARGET)
        else:
            spots = HCT_STANDARD_NORMAL.get(pos) or []
            target = _zone_centroid(spots)
        if is_away_offense:
            target = _flip(target)
        def_targets[pos] = target

    return off_targets, def_targets


def _player_id(player) -> str:
    return getattr(player, "player_id", str(id(player))) if player is not None else ""


def _player_read(player) -> int:
    """Standard player read (§4 The Read): IQ-weighted with a CH minority and a
    1-6 random multiplier."""
    attrs = getattr(player, "attributes", {}) or {}
    return int(((attrs.get("IQ", 0) * 0.8) + (attrs.get("CH", 0) * 0.2)) * random.randint(1, 6))


def _read_decision(player, broken: bool = False, dribble_alive: bool = True) -> str:
    """Map a read score to attack / pass / hold (§4).

    The mapping is **dynamic on the ball-handler's ``BH + AG``**:
      - **Strong handler** (``BH + AG > READ_STRONG_HANDLER_SUM``): a high read
        (``>= attack_t``) drives; a mid read (``> pass_t``) passes.
      - **Weak handler** (``BH + AG <= READ_STRONG_HANDLER_SUM``): INVERTED — a
        high read (``>= attack_t``) kicks it out (pass); a mid read (``> pass_t``)
        forces a drive (attack).

    ``broken=True`` applies the §5 reduced (open-floor) thresholds for BOTH
    branches. The low tier (read below ``pass_t``) is no longer a hard hold — it
    rolls ``READ_LOW_TIER_CHOICES`` (50% hold, 25% attack, 25% pass).
    ``dribble_alive=False`` (D21): the BH has picked up his dribble, so any
    ``attack`` result collapses to ``pass`` (no drive without a live dribble).
    """
    score = _player_read(player)
    attack_t = BROKEN_READ_ATTACK_THRESHOLD if broken else READ_ATTACK_THRESHOLD
    pass_t = BROKEN_READ_PASS_THRESHOLD if broken else READ_PASS_THRESHOLD

    attrs = getattr(player, "attributes", {}) or {}
    strong_handler = (attrs.get("BH", 0) + attrs.get("AG", 0)) > READ_STRONG_HANDLER_SUM

    if score >= attack_t:
        decision = "attack" if strong_handler else "pass"
    elif score > pass_t:
        decision = "pass" if strong_handler else "attack"
    else:
        decision = random.choice(READ_LOW_TIER_CHOICES)

    # D21: no live dribble → a drive is impossible; kick it out instead.
    if decision == "attack" and not dribble_alive:
        decision = "pass"
    return decision


def _steal_credit_defender(bh_defender, trapper):
    """Pick which defender is credited for a steal: the one with the higher
    steal composite (OD·0.4 + AG·0.4 + IQ·0.2). For a lone defender, that's him."""
    if trapper is None:
        return bh_defender

    def _steal_score(d):
        a = getattr(d, "attributes", {}) or {}
        return a.get("OD", 0) * 0.4 + a.get("AG", 0) * 0.4 + a.get("IQ", 0) * 0.2

    return trapper if _steal_score(trapper) > _steal_score(bh_defender) else bh_defender


def _select_d_foul_fouler(
    bh_defender,
    def_lineup,
    trapper=None,
    backcourt_pos: Tuple[str, ...] = HCT_BACKCOURT_POS,
    frontcourt_pos: Tuple[str, ...] = HCT_FRONTCOURT_POS,
) -> Tuple[Any, bool]:
    """§5 reach-in foul attribution. The on-ball (BH) defender's blow-by is the
    root cause of the foul, but the whistle lands on:

      - 60% the on-ball defender himself (a true reach-in),
      - 30% another backcourt defender who rotated to help — the ``trapper`` (when
        one exists) is the compensating fouler; otherwise a random other backcourt
        defender; falls back to the on-ball defender when none exist,
      - 10% a frontcourt defender committing an off-ball help foul to compensate;
        falls back to the on-ball defender when none exist.

    ``backcourt_pos`` / ``frontcourt_pos`` default to the static positional split
    ({PG,SG,SF} / {PF,C}) used by Standard Trap & Straight Pressure; Standard
    Diamond passes a per-step dynamic split (see ``_diamond_court_split``).

    Returns ``(fouler, is_reach_in)`` where ``is_reach_in`` is True only when the
    credited fouler is the on-ball defender — that flag drives the "Reaching In"
    announcement on the front end.
    """
    roll = random.random()
    if roll < HCT_DFOUL_PRIMARY_P:
        return bh_defender, True
    if roll < HCT_DFOUL_PRIMARY_P + HCT_DFOUL_BACKCOURT_P:
        if trapper is not None and trapper is not bh_defender:
            return trapper, False
        others = [
            def_lineup[p]
            for p in backcourt_pos
            if def_lineup.get(p) is not None and def_lineup.get(p) is not bh_defender
        ]
        if others:
            return random.choice(others), False
        return bh_defender, True
    frontcourt = [
        def_lineup[p] for p in frontcourt_pos if def_lineup.get(p) is not None
    ]
    if frontcourt:
        return random.choice(frontcourt), False
    return bh_defender, True


def _resolve_moment(
    off_team,
    def_team,
    ball_handler,
    bh_defender,
    trapper=None,
    exclude_steal: bool = False,
) -> Tuple[str, float, Any]:
    """§5 Pressure / Trap banded outcome (D8 attribute-driven).

    Returns ``(outcome, score_ratio, credited_player)`` where ``outcome`` ∈
    {"DEAD BALL", "STEAL", "O_FOUL", "D_FOUL", "POS_O", "NEUTRAL"}.
    ``exclude_steal`` (D21 broken-HCT cutoff): a full-speed drive collision is a
    charge/block/lost-handle situation, not a pickpocket — zero the steal weight
    so the defense-wins event re-normalizes across DEAD BALL / O_FOUL only.
    ``score_ratio`` is the 0..1 turnover point along the BH's drive path (only
    meaningful for DEAD BALL/STEAL). ``credited_player`` is the defender to
    credit (STEAL/D_FOUL) or ``None``.

    Structure: the existing banded gate decides who *wins* the moment; D8 then
    derives the foul/steal/turnover outcome from attributes + team attrs +
    aggression. See ``Dynamic_HCT_Turns.md`` §5 (Attribute-driven contest model).
    """
    off_attrs = getattr(off_team, "team_attributes", {}) or {}
    def_attrs = getattr(def_team, "team_attributes", {}) or {}

    pt_eff = float(def_attrs.get("pt_efficiency", 0) or 0)
    pt_opp = float(off_attrs.get("pt_opp_modifier", 0) or 0)
    off_chem = int((off_attrs.get("team_chemistry", 0) or 0) / 4)
    def_chem = int((def_attrs.get("team_chemistry", 0) or 0) / 4)
    discipline = float(def_attrs.get("discipline", 0) or 0)
    fight_off = float(off_attrs.get("fight", 0) or 0)

    d_score = calculate_defender_pressure_score(bh_defender, "man")
    if trapper is not None:
        d_score += 0.5 * calculate_defender_pressure_score(trapper, "man")
    d_score += pt_eff * random.randint(1, 6)

    base_handling = calculate_ball_handling_score(ball_handler)
    # Spec adds the pt_opp term (symmetric with d_score's pt_eff term); pt_opp == 0
    # is a natural no-op for addition.
    o_score = base_handling + pt_opp * random.randint(1, 6)

    agg = HCT_D8_AGG_MULT.get(_aggression_call(def_team), 1.0)
    bh = getattr(ball_handler, "attributes", {}) or {}
    ref = HCT_D8_REF

    # --- Defense wins the moment → STEAL / DEAD BALL / O_FOUL / no-event -----
    if d_score > o_score + (off_chem + pt_opp):
        m = d_score - o_score
        m_norm = _clampf(m / HCT_D8_M_REF, 0.0, 1.0)
        # OFFENSE fight resists ALL D-wins events (same scale as discipline on D_FOUL).
        p_event = _clampf(
            HCT_D8_DEF_WIN_BASE * m_norm * agg
            * (1.0 - HCT_D8_W_FIGHT * fight_off) * HCT_D8_GLOBAL_SCALAR,
            0.0, HCT_D8_P_EVENT_MAX,
        )
        if random.random() >= p_event:
            # No-event: BH retains; fall through to the normal advance/re-read.
            return "NEUTRAL", 1.0, None

        credited = _steal_credit_defender(bh_defender, trapper)
        cd = getattr(credited, "attributes", {}) or {}
        def_steal = cd.get("OD", 0) * 0.4 + cd.get("AG", 0) * 0.4 + cd.get("IQ", 0) * 0.2
        bh_secure = bh.get("CH", 0) * 0.4 + bh.get("BH", 0) * 0.4 + bh.get("IQ", 0) * 0.2
        bh_handle = bh.get("BH", 0) * 0.4 + bh.get("CH", 0) * 0.3 + bh.get("IQ", 0) * 0.3

        steal_factor = _clampf(
            (1.0 + HCT_D8_S_SENS * (def_steal - bh_secure) / ref
             + HCT_D8_W_PTEFF * pt_eff) * agg,
            HCT_D8_F_MIN, HCT_D8_F_MAX,
        )
        db_factor = _clampf(
            1.0 + HCT_D8_DB_SENS * (ref - bh_handle) / ref - HCT_D8_W_PTOPP * pt_opp,
            HCT_D8_F_MIN, HCT_D8_F_MAX,
        )
        ofoul_factor = _clampf(
            1.0 + HCT_D8_O_SENS_IQ * (cd.get("IQ", 0) - bh.get("IQ", 0)) / ref
            + HCT_D8_O_SENS_DISC * discipline / HCT_D8_DISC_SCALE,
            HCT_D8_F_MIN, HCT_D8_F_MAX,
        )
        steal_w = 0.0 if exclude_steal else HCT_D8_STEAL_W0 * steal_factor
        db_w = HCT_D8_DB_W0 * db_factor
        ofoul_w = HCT_D8_OFOUL_W0 * ofoul_factor

        choice = random.choices(
            ["STEAL", "DEAD BALL", "O_FOUL"], weights=[steal_w, db_w, ofoul_w]
        )[0]
        if choice == "STEAL":
            return "STEAL", random.uniform(0.2, 0.8), credited
        if choice == "O_FOUL":
            return "O_FOUL", 1.0, None
        return "DEAD BALL", random.uniform(0.2, 0.8), None

    # --- Offense wins the moment → POS_O, with a small D_FOUL on the blow-by --
    if o_score >= d_score + (def_chem + pt_eff):
        beaten_norm = _clampf((o_score - d_score) / HCT_D8_M_REF, 0.0, 1.0)
        ag_gap = _clampf(bh.get("AG", 0) - (getattr(bh_defender, "attributes", {}) or {}).get("AG", 0), 0.0, ref)
        p_dfoul = _clampf(
            HCT_D8_DFOUL_BASE * beaten_norm
            * (1.0 - HCT_D8_W_DISC_REACH * discipline)
            * (1.0 + HCT_D8_W_AG_BEATEN * ag_gap / ref)
            * agg * HCT_D8_GLOBAL_SCALAR,
            0.0, HCT_D8_P_DFOUL_MAX,
        )
        if random.random() < p_dfoul:
            return "D_FOUL", 1.0, bh_defender
        return "POS_O", 1.0, None

    return "NEUTRAL", 1.0, None


def _basket_dir(is_away_offense: bool) -> int:
    """Advance direction in x toward the offense's basket (+1 home, -1 away)."""
    return -1 if is_away_offense else 1


def _crossed_half_court(x: float, is_away_offense: bool) -> bool:
    return x <= 50 if is_away_offense else x >= 50


def _past_primary_safe_area(xy: Dict[str, Any], is_away_offense: bool) -> bool:
    """BH advanced beyond the PSA band into the deep frontcourt (x>64 home /
    x<36 away). Gates the Attack Basket Area (§7 goal achievement)."""
    x = xy["x"]
    return x < (100 - PSA_X_MAX) if is_away_offense else x > PSA_X_MAX


def _in_attack_basket_area(xy: Dict[str, Any], is_away_offense: bool) -> bool:
    """§7 / D21 Attack Basket Area — the sole trap-break zone: past the PSA band
    (x>64 home / x<36 away) AND within the y 10-40 band (D22)."""
    if not (ATTACK_BASKET_Y_MIN <= xy["y"] <= ATTACK_BASKET_Y_MAX):
        return False
    return _past_primary_safe_area(xy, is_away_offense)


def _count_in_attack_basket(
    coords: Dict[str, Dict[str, int]], is_away_offense: bool
) -> int:
    """Number of players (by position) inside the Attack Basket Area."""
    return sum(
        1 for p in POSITIONS if _in_attack_basket_area(coords[p], is_away_offense)
    )


def _clamp_xy(xy: Dict[str, Any]) -> Dict[str, int]:
    """Universal animation clamp (§4) for a single target."""
    clamped = clamp_animation_grid_coords({"x": xy["x"], "y": xy["y"]}, result_type="HCT") or xy
    return {"x": int(round(clamped["x"])), "y": int(round(clamped["y"]))}


def _converge_xy(bh_xy: Dict[str, Any], is_away_offense: bool) -> Dict[str, int]:
    """A defender's spot when engaging the BH: between BH and the basket."""
    offset = -STEP_2_DEFENDER_X_OFFSET if is_away_offense else STEP_2_DEFENDER_X_OFFSET
    return _clamp_xy({"x": int(bh_xy["x"] + offset), "y": int(bh_xy["y"])})


def _is_ahead(def_xy: Dict[str, Any], bh_xy: Dict[str, Any], is_away_offense: bool) -> bool:
    """True if the defender's x is closer to the offense's basket than the BH's."""
    return def_xy["x"] < bh_xy["x"] if is_away_offense else def_xy["x"] > bh_xy["x"]


def _in_range_defenders(
    bh_xy: Dict[str, Any], def_coords: Dict[str, Dict[str, int]]
) -> List[str]:
    """Defender positions within ``MOMENT_RANGE`` euclidean spots of the BH,
    sorted nearest-first."""
    in_range = [
        pos for pos in POSITIONS if _euclid(bh_xy, def_coords[pos]) <= MOMENT_RANGE
    ]
    in_range.sort(key=lambda pos: _euclid(bh_xy, def_coords[pos]))
    return in_range


def _detect_moment(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
) -> Tuple[str, List[str]]:
    """§5 continuous distance detection.

    Returns ``(kind, in_range)`` where ``kind`` ∈ {"none", "pressure", "trap"}
    and ``in_range`` is the nearest-first list of in-range defender positions.
    A trap needs ≥2 in range with ≥1 ahead of the BH; pressure needs ≥1 in
    range that is ahead.
    """
    in_range = _in_range_defenders(bh_xy, def_coords)
    ahead = [p for p in in_range if _is_ahead(def_coords[p], bh_xy, is_away_offense)]
    if len(in_range) >= 2 and ahead:
        return "trap", in_range
    if in_range and ahead:
        return "pressure", in_range
    return "none", in_range


def _select_trappers(
    in_range: List[str],
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
) -> Tuple[str, str]:
    """§5 trapper selection (universal, band-based). Returns
    ``(bh_defender_pos, trapper_pos)``.

    The **primary (on-ball) defender** is the in-range defender whose own
    position sits in the same vertical band as the ball (band buckets per
    ``_diamond_band`` on the *defender's* y); ties → the in-range defender
    closest to the BH; none in-band → closest to the BH. The **trapper** is the
    next-closest of the remaining in-range defenders. ``in_range`` is
    nearest-first.

    This replaces the old "defensive PG is always on-ball" rule across every HCT
    play (Standard Trap / Straight Pressure / Standard Diamond), so reach-ins and
    D_FOULs land on whoever is actually defending the ball's band rather than
    always the PG. For Standard Diamond it naturally resolves to the band's
    assigned defender (center → center_bc_defender; upper/lower → that wing).
    """
    ball_band = _diamond_band(bh_xy["y"])
    in_band = [p for p in in_range if _diamond_band(def_coords[p]["y"]) == ball_band]
    primary = in_band[0] if in_band else in_range[0]
    trapper = next(p for p in in_range if p != primary)
    return primary, trapper


def _select_pass_receiver(
    bh_pos: str,
    off_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    exclude: Optional[set] = None,
) -> str:
    """§6 pass: the ball goes to one of the two teammates closest to the BH
    (chosen at random between those two).

    Over-and-back guard: once the BH has crossed half-court he may not pass to a
    teammate still in the backcourt (x<50 home / x>50 away) without an
    over-and-back violation. For now we *prevent* it — if one of the two closest
    teammates would be a violation and the other would not, the legal teammate
    is chosen. (Detecting an actual over-and-back and processing it as a
    dead-ball turnover is a later item; see the §11 outstanding list.)

    ``exclude`` drops positions from the pool (FCP: SF still at the BIP spot).
    """
    skip = {bh_pos} | set(exclude or ())
    others = [p for p in POSITIONS if p not in skip]
    if not others:
        others = [p for p in POSITIONS if p != bh_pos]
    others.sort(key=lambda p: _euclid(off_coords[bh_pos], off_coords[p]))
    candidates = others[:2]
    if _crossed_half_court(off_coords[bh_pos]["x"], is_away_offense):
        legal = [
            p
            for p in candidates
            if _crossed_half_court(off_coords[p]["x"], is_away_offense)
        ]
        if legal:
            candidates = legal
    return random.choice(candidates)


def _choose_shot_attempt(
    player,
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    dribble_alive: bool = True,
) -> str:
    """§7 shot-attempt tree: returns "shoot" / "drive" / "pass".

    Optimal: SH>80 → shoot; elif SC+AG>105 → drive; else pass. With no defender
    in range the BH always drives (or passes to a teammate closer to the basket —
    the pass leaf is 2D-2c). Otherwise a read gates optimal-vs-random: read>200 →
    the optimal option, else a random option. ``dribble_alive=False`` (D21): the
    BH can't drive — a drive choice falls back to a shot.
    """
    attrs = getattr(player, "attributes", {}) or {}
    sh = attrs.get("SH", 0)
    sc = attrs.get("SC", 0)
    ag = attrs.get("AG", 0)
    if sh > SHOOT_SH_THRESHOLD:
        optimal = "shoot"
    elif sc + ag > DRIVE_SCAG_THRESHOLD:
        optimal = "drive"
    else:
        optimal = "pass"
    if not _in_range_defenders(bh_xy, def_coords):
        choice = "drive"
    elif _player_read(player) > GOAL_ACHIEVEMENT_READ_THRESHOLD:
        choice = optimal
    else:
        choice = random.choice(("shoot", "drive", "pass"))
    if choice == "drive" and not dribble_alive:
        return "shoot"
    return choice


def _select_top_level_pass_receiver(
    bh_pos: str,
    off_coords: Dict[str, Dict[str, int]],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
):
    """§7 top-level pass receiver (distinct from the §6 backcourt pass).

    Candidate pool = teammates past x=64 (toward the basket). Default = the
    teammate closest to the BH. Open-rim override: a teammate within 9 euclidean
    of the basket with **no** defender within 9 of him receives instead (random
    among qualifiers). Returns the receiver position, or ``None`` if no teammate
    is past x=64 (caller falls back to a solo finish). The forward-only pool
    means the over-and-back guard is satisfied by construction.
    """
    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    basket = {"x": float(rim["x"]), "y": float(rim["y"])}

    def _past_64(c: Dict[str, Any]) -> bool:
        return (100 - c["x"]) > 64 if is_away_offense else c["x"] > 64

    pool = [p for p in POSITIONS if p != bh_pos and _past_64(off_coords[p])]
    if not pool:
        return None
    open_rim = [
        p
        for p in pool
        if _euclid(off_coords[p], basket) <= TOP_PASS_OPEN_RIM_RADIUS
        and all(
            _euclid(off_coords[p], def_coords[d]) > TOP_PASS_OPEN_RIM_RADIUS
            for d in POSITIONS
        )
    ]
    if open_rim:
        return random.choice(open_rim)
    return min(pool, key=lambda p: _euclid(off_coords[bh_pos], off_coords[p]))


def _determine_shift(bh_y: float) -> str:
    """§6 shift trigger on ball-handler y."""
    if bh_y < SHIFT_LOWER_Y:
        return "lower"
    if bh_y > SHIFT_UPPER_Y:
        return "upper"
    return "normal"


def _spot(name: str, is_away_offense: bool) -> Dict[str, int]:
    """An ``HCO_STRING_SPOTS`` spot, flipped in x for away offense."""
    s = HCO_STRING_SPOTS[name]
    return _flip(s) if is_away_offense else {"x": int(s["x"]), "y": int(s["y"])}


def _aba_half(xy: Dict[str, Any]) -> str:
    """D22 ABA half for offender counting: upper = y ≥ 26, lower = y ≤ 25."""
    return "upper" if xy["y"] >= 26 else "lower"


def _ball_band(y: float) -> str:
    """D22 ball band by the ball's y: upper > 28, lower < 22, else center."""
    if y > 28:
        return "upper"
    if y < 22:
        return "lower"
    return "center"


def _pfc_help_denial(
    bh_xy: Dict[str, Any],
    off_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    half: str,
) -> Dict[str, int]:
    """D22 not-in-ABA help/denial for the half-side defender (C upper / PF lower).

    Drop to the wing if no offender occupies that ABA half; else read the
    deepest such offender — deny the BH→offender entry-pass lane (60% from the
    BH) if he is *deeper than the bird*, otherwise sit at the bird.
    """
    wing = _spot("upper wing" if half == "upper" else "lower wing", is_away_offense)
    bird = _spot("upper bird" if half == "upper" else "lower bird", is_away_offense)
    occupants = [
        p
        for p in POSITIONS
        if _in_attack_basket_area(off_coords[p], is_away_offense)
        and _aba_half(off_coords[p]) == half
    ]
    if not occupants:
        return wing
    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    rim_xy = {"x": float(rim["x"]), "y": float(rim["y"])}
    # Closest to the basket; tie-break → higher x (per spec).
    best = sorted(
        occupants, key=lambda p: (_euclid(off_coords[p], rim_xy), -off_coords[p]["x"])
    )[0]
    off_xy = off_coords[best]
    deeper_than_bird = (
        off_xy["x"] < bird["x"] if is_away_offense else off_xy["x"] > bird["x"]
    )
    if deeper_than_bird:
        return _clamp_xy(_interpolate(bh_xy, off_xy, 0.6))
    return bird


def _pf_c_targets(
    bh_xy: Dict[str, Any],
    off_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
) -> Dict[str, Dict[str, int]]:
    """D22 ball-reactive defensive PF/C coverage targets (replaces their static
    NORMAL-centroid anchor for the whole possession). C = upper-half defender,
    PF = lower-half defender; both move at AG sprint (see ``_move_defense``)."""
    midLane = _spot("midLane", is_away_offense)
    basketSpot = _spot("basketSpot", is_away_offense)
    topLane = _spot("topLane", is_away_offense)
    key = _spot("key", is_away_offense)
    band = _ball_band(bh_xy["y"])
    # "Defend the BH" close-out (between the BH and the basket). The §5 cutoff
    # solver hooks in here once the BH gains an in-ABA drift target (D22 note).
    defend_bh = _converge_xy(bh_xy, is_away_offense)

    if _in_attack_basket_area(bh_xy, is_away_offense):
        if band == "center":
            return {"C": basketSpot, "PF": defend_bh}
        if band == "upper":
            return {"C": defend_bh, "PF": midLane}
        return {"PF": defend_bh, "C": midLane}  # lower band

    # Ball not in the ABA (incl. the backcourt).
    if band == "center":
        mid = _clamp_xy(
            {"x": int(round((key["x"] + topLane["x"]) / 2)), "y": key["y"]}
        )
        return {"PF": mid, "C": midLane}
    if band == "upper":
        return {
            "PF": topLane,
            "C": _pfc_help_denial(bh_xy, off_coords, is_away_offense, "upper"),
        }
    # lower band — mirror: C anchors topLane, PF runs the lower help/denial.
    return {
        "C": topLane,
        "PF": _pfc_help_denial(bh_xy, off_coords, is_away_offense, "lower"),
    }


def _defense_targets(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    off_coords: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, Dict[str, int]]:
    """§6 defensive formation targets around the BH (pure — no mutation).

    Upper/lower shift → two designated trappers form the standard HC trap
    (reusing ``compute_hct_trap_formation``) plus a center defender; normal
    shift → the defensive PG pressures the BH. Non-engaged backcourt defenders
    hold at their current spot. **PF/C (D22):** when ``off_coords`` is provided
    they follow the ball-reactive coverage model (``_pf_c_targets``), overriding
    the trap/hold default; otherwise they hold (back-compat).
    """
    targets: Dict[str, Dict[str, int]] = {pos: dict(def_coords[pos]) for pos in POSITIONS}
    shift = _determine_shift(bh_xy["y"])
    if shift in ("upper", "lower"):
        trap = compute_hct_trap_formation(bh_xy, shift, is_away_offense=is_away_offense)
        for pos, xy in trap.items():
            targets[pos] = _clamp_xy(xy)
        # Center defender (remaining backcourt guard): y=25, x ±4 toward basket.
        backcourt = {"PG", "SG", "SF"}
        center_candidates = [p for p in backcourt if p not in trap]
        if center_candidates:
            center_pos = center_candidates[0]
            cx = bh_xy["x"] + _basket_dir(is_away_offense) * 4
            targets[center_pos] = _clamp_xy({"x": int(cx), "y": 25})
    else:
        targets["PG"] = _converge_xy(bh_xy, is_away_offense)
    # D22: the PF/C follow the ball-reactive coverage model for the whole
    # possession (PG/SG/SF unchanged above).
    if off_coords is not None:
        pfc = _pf_c_targets(bh_xy, off_coords, is_away_offense)
        targets["PF"] = _clamp_xy(pfc["PF"])
        targets["C"] = _clamp_xy(pfc["C"])
    return targets


# --- Straight Pressure (§13.6 — play #2) ---------------------------------------
# Man-to-man backcourt scheme. The three backcourt defenders (PG/SG/SF) lock onto
# a man at the converge and stick until a stop event, EXCEPT a man who enters the
# ABA is released and the freed defender fills the next open role:
#   rover/trapper (tracks the live BH) → key (sits at key, toggling to a wing by
#   the BH's y, and mans up on any offender returning to the backcourt) → wings.
# A real trap re-forms only via the rover (see ``StraightPressure.detect_moment``).
# PF/C inherit the Standard D22 zone coverage (``_pf_c_targets``).
#
# Deny spot: fraction from the live BH toward the guarded man (ball-side denial).
STRAIGHT_PRESSURE_DENY_FRACTION = 0.6
# Off-ball backcourt defenders (def PG always takes the ball handler).
STRAIGHT_PRESSURE_OFFBALL_DEFENDERS = ("SG", "SF")
# Backcourt boundary: an offender with x ≥ 64 (home) / x ≤ 36 (away) is frontcourt,
# NOT a backcourt offender (distinct from the ABA y-band test).
STRAIGHT_PRESSURE_BACKCOURT_X = 64
# Key-role wing toggle thresholds (BH y): > upper → upper wing; < lower → lower.
STRAIGHT_PRESSURE_KEY_UPPER_Y = 28
STRAIGHT_PRESSURE_KEY_LOWER_Y = 22


def _is_backcourt_offender(xy: Dict[str, Any], is_away_offense: bool) -> bool:
    """A backcourt offensive player: x < 64 (home) / x > 36 (away)."""
    if is_away_offense:
        return xy["x"] > (100 - STRAIGHT_PRESSURE_BACKCOURT_X)
    return xy["x"] < STRAIGHT_PRESSURE_BACKCOURT_X


def _match_off_pos(off_coords: Dict[str, Dict[str, int]], xy: Dict[str, Any]) -> str:
    """The offensive position currently at ``xy`` (identity first, then value)."""
    for p in POSITIONS:
        if off_coords[p] is xy:
            return p
    for p in POSITIONS:
        if off_coords[p]["x"] == xy["x"] and off_coords[p]["y"] == xy["y"]:
            return p
    return "PG"


def _nearest_matchup_two(
    defs: List[str],
    men: List[str],
    def_coords: Dict[str, Dict[str, int]],
    off_coords: Dict[str, Dict[str, int]],
) -> Dict[str, str]:
    """Pair two defenders to two men with the smaller total distance (no cross)."""
    d1, d2 = defs
    m1, m2 = men
    straight = _euclid(def_coords[d1], off_coords[m1]) + _euclid(def_coords[d2], off_coords[m2])
    crossed = _euclid(def_coords[d1], off_coords[m2]) + _euclid(def_coords[d2], off_coords[m1])
    return {d1: m1, d2: m2} if straight <= crossed else {d1: m2, d2: m1}


def _straight_pressure_begin(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    off_coords: Optional[Dict[str, Dict[str, int]]],
    is_away_offense: bool,
) -> Dict[str, Any]:
    """Lock the initial man assignments + roles at the converge (§13.6).

    def PG → the BH. The two off-ball defenders (SG/SF) cover, by nearest-matchup,
    the two non-BH backcourt offenders closest to the BH (higher-y / lower-y). With
    one such offender the spare defender roves; with none, one roves and one keys.
    """
    state: Dict[str, Any] = {
        "assignment": {},     # def_pos -> off_pos (man defenders, incl. PG→BH)
        "rover": None,        # def_pos or None
        "key": None,          # def_pos or None
        "wings": {},          # def_pos -> "upper" | "lower"
        "entered_aba": set(),  # off positions that have visited the ABA
    }
    offball = list(STRAIGHT_PRESSURE_OFFBALL_DEFENDERS)
    if off_coords is None:
        state["assignment"]["PG"] = "PG"
        state["rover"] = offball[0]
        state["key"] = offball[1]
        return state

    bh_off = _match_off_pos(off_coords, bh_xy)
    state["assignment"]["PG"] = bh_off

    candidates = [
        p
        for p in POSITIONS
        if p != bh_off and _is_backcourt_offender(off_coords[p], is_away_offense)
    ]
    candidates.sort(key=lambda p: _euclid(off_coords[p], bh_xy))

    if len(candidates) >= 2:
        two = sorted(candidates[:2], key=lambda p: off_coords[p]["y"])
        lower_y, higher_y = two[0], two[1]
        state["assignment"].update(
            _nearest_matchup_two(offball, [higher_y, lower_y], def_coords, off_coords)
        )
    elif len(candidates) == 1:
        man = candidates[0]
        nearest = min(offball, key=lambda d: _euclid(def_coords[d], off_coords[man]))
        other = offball[0] if offball[1] == nearest else offball[1]
        state["assignment"][nearest] = man
        state["rover"] = other
    else:
        rover = min(offball, key=lambda d: _euclid(def_coords[d], bh_xy))
        other = offball[0] if offball[1] == rover else offball[1]
        state["rover"] = rover
        state["key"] = other
    return state


def _straight_pressure_assign_role(
    state: Dict[str, Any],
    def_pos: str,
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
) -> None:
    """A freed defender (his man entered the ABA) fills the next open role:
    rover → key → wings (future-proof: the current key + this defender split to
    the two wings, each taking the nearer one)."""
    if state["rover"] is None:
        state["rover"] = def_pos
    elif state["key"] is None:
        state["key"] = def_pos
    else:
        kd = state["key"]
        uw = _spot("upper wing", is_away_offense)
        lw = _spot("lower wing", is_away_offense)
        straight = _euclid(def_coords[kd], uw) + _euclid(def_coords[def_pos], lw)
        crossed = _euclid(def_coords[kd], lw) + _euclid(def_coords[def_pos], uw)
        state["wings"] = (
            {kd: "upper", def_pos: "lower"}
            if straight <= crossed
            else {kd: "lower", def_pos: "upper"}
        )
        state["key"] = None


def _straight_pressure_key_spot(
    bh_xy: Dict[str, Any], is_away_offense: bool
) -> Dict[str, int]:
    """Key-role anchor: upper wing if BH y > 28, lower wing if BH y < 22, else key."""
    if bh_xy["y"] > STRAIGHT_PRESSURE_KEY_UPPER_Y:
        return _spot("upper wing", is_away_offense)
    if bh_xy["y"] < STRAIGHT_PRESSURE_KEY_LOWER_Y:
        return _spot("lower wing", is_away_offense)
    return _spot("key", is_away_offense)


def _straight_pressure_targets(
    state: Dict[str, Any],
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    off_coords: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, Dict[str, int]]:
    """§13.6 man-to-man targets. Mutates ``state`` for the man→ABA role transitions.

    Each man defender converges on the BH if his man currently holds the ball, else
    denies ball-side (on the BH→man line). The rover tracks the live BH; the key
    sits at the key/wing toggle or mans up on a returning offender; wing defenders
    sit on their wing. PF/C inherit the Standard D22 zone coverage.
    """
    targets: Dict[str, Dict[str, int]] = {pos: dict(def_coords[pos]) for pos in POSITIONS}

    if off_coords is None:
        # Terminal collapse beat (stopper): man defenders + rover converge on the BH.
        for d in state["assignment"]:
            targets[d] = _converge_xy(bh_xy, is_away_offense)
        if state["rover"] is not None:
            targets[state["rover"]] = _converge_xy(bh_xy, is_away_offense)
        return targets

    bh_off = _match_off_pos(off_coords, bh_xy)

    # Track which offenders have visited the ABA this possession.
    for p in POSITIONS:
        if _in_attack_basket_area(off_coords[p], is_away_offense):
            state["entered_aba"].add(p)

    # 1) Release any man defender whose man entered the ABA → fill the next role.
    released = [
        d
        for d, m in state["assignment"].items()
        if _in_attack_basket_area(off_coords[m], is_away_offense)
    ]
    for d in released:
        del state["assignment"][d]
        _straight_pressure_assign_role(state, d, def_coords, is_away_offense)

    # 2) The key defender mans up on an offender returning to the backcourt from
    #    the ABA (takes precedence over the key/wing toggle).
    if state["key"] is not None:
        guarded = set(state["assignment"].values())
        returners = [
            p
            for p in POSITIONS
            if p in state["entered_aba"]
            and p != bh_off
            and p not in guarded
            and _is_backcourt_offender(off_coords[p], is_away_offense)
            and not _in_attack_basket_area(off_coords[p], is_away_offense)
        ]
        if returners:
            kd = state["key"]
            man = min(returners, key=lambda p: _euclid(def_coords[kd], off_coords[p]))
            state["assignment"][kd] = man
            state["key"] = None

    # 3) Compute targets per current assignments / roles.
    for d, m in state["assignment"].items():
        if m == bh_off:
            targets[d] = _converge_xy(bh_xy, is_away_offense)  # man has the ball → on-ball
        else:
            targets[d] = _clamp_xy(
                _interpolate(bh_xy, off_coords[m], STRAIGHT_PRESSURE_DENY_FRACTION)
            )  # deny ball-side
    if state["rover"] is not None:
        targets[state["rover"]] = _converge_xy(bh_xy, is_away_offense)
    if state["key"] is not None:
        targets[state["key"]] = _clamp_xy(
            _straight_pressure_key_spot(bh_xy, is_away_offense)
        )
    for d, side in state["wings"].items():
        targets[d] = _clamp_xy(
            _spot("upper wing" if side == "upper" else "lower wing", is_away_offense)
        )

    # PF/C — identical D22 ball-reactive coverage as Standard Trap.
    pfc = _pf_c_targets(bh_xy, off_coords, is_away_offense)
    targets["PF"] = _clamp_xy(pfc["PF"])
    targets["C"] = _clamp_xy(pfc["C"])
    return targets


# --- Standard Diamond (§13.7 — play #3) ---------------------------------------
# A 1-4 alignment. The ``center_bc_defender`` pressures the BH up top; ``pos1``
# anchors a deep vertical-triangle zone in front of the rim (denying ABA offenders
# by band); ``pos2``/``pos3`` are mirrored upper/lower trap-or-help wings; ``pos4``
# is a stay-home key safety + pass disruptor. Roles → real positions resolve via
# ``_diamond_alias_map`` (default center_bc_defender=PG → pos1=SG/pos2=SF/pos3=PF/
# pos4=C) so future position customization just works. The universal band-based
# ``_select_trappers`` picks the on-ball primary; PF/C zone coverage is NOT used.
DIAMOND_DENY_X_GAP = 2            # deny dest sits 2 x-spots BH-side of the offender
DIAMOND_POS4_DENY_RANGE = 8.0     # pos4 mans up on an offender within this of his spot
DIAMOND_WING_AHEAD_MIN = 3        # center-band wing x lead ahead of the BH
DIAMOND_WING_AHEAD_MAX = 8
DIAMOND_JITTER = 3                # ± per-step positional jitter
DIAMOND_POS4_BAND_DY = 3          # pos4 key-anchor y shift by band


def _diamond_band(y: float) -> str:
    """Standard Diamond band by y: center 20–30 (inclusive), upper > 30, lower < 20."""
    if y > 30:
        return "upper"
    if y < 20:
        return "lower"
    return "center"


def _diamond_alias_map(center_bc_defender: str = "PG") -> Dict[str, str]:
    """Map ``pos1..pos4`` → real defender positions, excluding the
    ``center_bc_defender`` (the defensive analog of a set play's target_shooter).
    Mirrors ``_alias_map``. Default center_bc_defender=PG → pos1=SG, pos2=SF,
    pos3=PF, pos4=C."""
    order = ["PG", "SG", "SF", "PF", "C"]
    cbd = center_bc_defender.upper()
    remaining = [p for p in order if p != cbd]
    return {f"pos{i + 1}": pos for i, pos in enumerate(remaining)}


def _diamond_deny_xy(
    offender_xy: Dict[str, Any], is_away_offense: bool
) -> Dict[str, int]:
    """Deny destination: 2 x-spots toward the BH from the offender, same y."""
    return _clamp_xy(
        {
            "x": int(offender_xy["x"]) - DIAMOND_DENY_X_GAP * _basket_dir(is_away_offense),
            "y": int(offender_xy["y"]),
        }
    )


def _diamond_offender_half(off_xy: Dict[str, Any]) -> str:
    """Vertical half of an offender (matches ``_aba_half``): upper y≥26 / lower y≤25."""
    return "upper" if off_xy["y"] >= 26 else "lower"


def _diamond_start_formation(
    is_away_offense: bool, center_bc_defender: str = "PG"
) -> Dict[str, Dict[str, int]]:
    """Standard Diamond initial alignment (home orientation, flipped for away):
    center_bc_defender up top (x 44–50, y 23–27); pos1 at midLane (y ±5);
    pos2/pos3 at upper/lower deepWing (x & y ±3); pos4 at the key."""
    alias = _diamond_alias_map(center_bc_defender)
    midlane = _spot("midLane", is_away_offense)
    key = _spot("key", is_away_offense)
    up_dw = _spot("deep upper wing", is_away_offense)
    lo_dw = _spot("deep lower wing", is_away_offense)
    cbd = center_bc_defender.upper()
    cbd_xy = {"x": random.randint(44, 50), "y": random.randint(23, 27)}
    out: Dict[str, Dict[str, int]] = {
        cbd: _clamp_xy(_flip(cbd_xy) if is_away_offense else cbd_xy),
        alias["pos1"]: _clamp_xy(
            {"x": midlane["x"], "y": midlane["y"] + random.randint(-5, 5)}
        ),
        alias["pos2"]: _clamp_xy(
            {
                "x": up_dw["x"] + random.randint(-3, 3),
                "y": up_dw["y"] + random.randint(-3, 3),
            }
        ),
        alias["pos3"]: _clamp_xy(
            {
                "x": lo_dw["x"] + random.randint(-3, 3),
                "y": lo_dw["y"] + random.randint(-3, 3),
            }
        ),
        alias["pos4"]: dict(key),
    }
    return out


def _diamond_wing_target(
    wing_pos: str,
    side: str,
    band: str,
    bh_xy: Dict[str, Any],
    bh_off: str,
    def_coords: Dict[str, Dict[str, int]],
    off_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
) -> Dict[str, int]:
    """§13.7 mirrored wing (pos2 upper / pos3 lower)."""
    deep_spot = _spot(
        "deep upper wing" if side == "upper" else "deep lower wing", is_away_offense
    )
    if band == "center":
        # Hold near the deepWing start, leading the BH slightly toward the basket.
        return _clamp_xy(
            {
                "x": int(bh_xy["x"])
                + _basket_dir(is_away_offense)
                * random.randint(DIAMOND_WING_AHEAD_MIN, DIAMOND_WING_AHEAD_MAX),
                "y": deep_spot["y"] + random.randint(-DIAMOND_JITTER, DIAMOND_JITTER),
            }
        )
    if band == side:
        # Ball in this wing's vertical half → trap if in range; else help-deny an
        # off-ball offender in his area (x≤64, his half) closest to the BH; else
        # move in to execute the trap.
        if _euclid(bh_xy, def_coords[wing_pos]) <= MOMENT_RANGE:
            return _converge_xy(bh_xy, is_away_offense)
        area = [
            off_coords[p]
            for p in POSITIONS
            if p != bh_off
            and not _past_primary_safe_area(off_coords[p], is_away_offense)
            and _diamond_offender_half(off_coords[p]) == side
        ]
        if area:
            return _diamond_deny_xy(min(area, key=lambda c: _euclid(bh_xy, c)), is_away_offense)
        return _converge_xy(bh_xy, is_away_offense)
    # Ball in the opposite half → float to a random help spot on his own side.
    choices = [
        "midLane",
        "topLane",
        "upper midPost" if side == "upper" else "lower midPost",
        "upper highPost" if side == "upper" else "lower highPost",
    ]
    return _spot(random.choice(choices), is_away_offense)


def _diamond_pos4_target(
    band: str,
    bh_xy: Dict[str, Any],
    bh_off: str,
    off_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
) -> Dict[str, int]:
    """§13.7 pos4 — key-anchored stay-home safety + pass disruptor."""
    key = _spot("key", is_away_offense)
    if band == "upper":
        anchor = {"x": key["x"], "y": key["y"] + DIAMOND_POS4_BAND_DY}
    elif band == "lower":
        anchor = {"x": key["x"], "y": key["y"] - DIAMOND_POS4_BAND_DY}
    else:
        anchor = {"x": key["x"], "y": key["y"]}
    anchor = {
        "x": anchor["x"] + random.randint(-DIAMOND_JITTER, DIAMOND_JITTER),
        "y": anchor["y"] + random.randint(-DIAMOND_JITTER, DIAMOND_JITTER),
    }
    # Man up on the nearest-to-BH off-ball offender within range of his spot,
    # slotting into the BH→offender passing lane (midpoint). Ties broken randomly.
    near = [
        off_coords[p]
        for p in POSITIONS
        if p != bh_off and _euclid(off_coords[p], anchor) <= DIAMOND_POS4_DENY_RANGE
    ]
    if near:
        random.shuffle(near)
        target_off = min(near, key=lambda c: _euclid(bh_xy, c))
        return _clamp_xy(_interpolate(bh_xy, target_off, 0.5))
    return _clamp_xy(anchor)


def _diamond_targets(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    off_coords: Optional[Dict[str, Dict[str, int]]] = None,
    center_bc_defender: str = "PG",
) -> Dict[str, Dict[str, int]]:
    """§13.7 Standard Diamond per-step defensive targets (pure). Behavior applies
    while the ball is short of the ABA (x≤64); once the BH reaches the ABA the
    shared loop hands off to the broken-HCT/Fast-Break defense."""
    alias = _diamond_alias_map(center_bc_defender)
    cbd = center_bc_defender.upper()
    pos1, pos2, pos3, pos4 = alias["pos1"], alias["pos2"], alias["pos3"], alias["pos4"]
    targets: Dict[str, Dict[str, int]] = {pos: dict(def_coords[pos]) for pos in POSITIONS}

    # center_bc_defender always tracks the BH (on-ball pressure / trapper).
    targets[cbd] = _converge_xy(bh_xy, is_away_offense)

    band = _diamond_band(bh_xy["y"])

    if off_coords is None:
        # Terminal collapse beat (stopper): bring the band's wing in to finish.
        if band == "upper":
            targets[pos2] = _converge_xy(bh_xy, is_away_offense)
        elif band == "lower":
            targets[pos3] = _converge_xy(bh_xy, is_away_offense)
        return targets

    bh_off = _match_off_pos(off_coords, bh_xy)
    midlane_x = _spot("midLane", is_away_offense)["x"]

    # --- pos1: deep vertical-triangle zone in front of the rim ----------------
    if band == "center":
        targets[pos1] = _clamp_xy(
            {"x": midlane_x, "y": int(bh_xy["y"]) + random.randint(-DIAMOND_JITTER, DIAMOND_JITTER)}
        )
    else:
        aba_offenders = [
            off_coords[p]
            for p in POSITIONS
            if p != bh_off
            and _past_primary_safe_area(off_coords[p], is_away_offense)
            and _diamond_offender_half(off_coords[p]) == band
        ]
        if aba_offenders:
            closest_to_basket = max(
                aba_offenders, key=lambda c: c["x"] * _basket_dir(is_away_offense)
            )
            targets[pos1] = _diamond_deny_xy(closest_to_basket, is_away_offense)
        else:
            targets[pos1] = _spot(
                "upper bird" if band == "upper" else "lower bird", is_away_offense
            )

    # --- pos2 / pos3: mirrored upper / lower wings ----------------------------
    targets[pos2] = _diamond_wing_target(
        pos2, "upper", band, bh_xy, bh_off, def_coords, off_coords, is_away_offense
    )
    targets[pos3] = _diamond_wing_target(
        pos3, "lower", band, bh_xy, bh_off, def_coords, off_coords, is_away_offense
    )

    # --- pos4: stay-home key safety + pass disruptor --------------------------
    targets[pos4] = _diamond_pos4_target(band, bh_xy, bh_off, off_coords, is_away_offense)

    return targets


def _diamond_select_trappers(
    in_range: List[str],
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    center_bc_defender: str = "PG",
) -> Tuple[str, str]:
    """§13.7 band→role primary/trapper for Standard Diamond. Unlike the geometric
    default, the on-ball **primary** is the band's *assigned* defender — center →
    ``center_bc_defender``; upper → ``pos2``; lower → ``pos3`` — because the
    center_bc_defender chases the BH in every band (so a pure geometric rule would
    always pick him). When the assigned man isn't in range, fall back to the
    nearest in-range defender. The **trapper** is the ``center_bc_defender`` on a
    vertical-half trap (he's the help man), else the next-closest in-range
    defender."""
    alias = _diamond_alias_map(center_bc_defender)
    cbd = center_bc_defender.upper()
    band = _diamond_band(bh_xy["y"])
    assigned = cbd if band == "center" else (alias["pos2"] if band == "upper" else alias["pos3"])
    primary = assigned if assigned in in_range else in_range[0]
    if primary != cbd and cbd in in_range:
        trapper = cbd
    else:
        trapper = next(p for p in in_range if p != primary)
    return primary, trapper


def _diamond_court_split(
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    center_bc_defender: str = "PG",
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Dynamic backcourt/frontcourt split for the §5 D_FOUL spread under Standard
    Diamond: a defender is *frontcourt* if his current x is past the ABA boundary
    (x>64 home / x<36 away), EXCEPT ``pos4`` (the key safety) is always counted
    backcourt (he floats forward but stays in backcourt help calculations)."""
    pos4 = _diamond_alias_map(center_bc_defender)["pos4"]
    backcourt: List[str] = []
    frontcourt: List[str] = []
    for p in POSITIONS:
        if p != pos4 and _past_primary_safe_area(def_coords[p], is_away_offense):
            frontcourt.append(p)
        else:
            backcourt.append(p)
    return tuple(backcourt), tuple(frontcourt)


def _position_defense(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    off_coords: Optional[Dict[str, Dict[str, int]]] = None,
    play: Any = None,
) -> None:
    """Snap the defense onto its §6 targets in place (instantaneous reposition —
    used where the defense is *set* at once, e.g. the pass-defense formation).
    ``off_coords`` feeds the D22 PF/C coverage. ``play`` selects the formation seam
    (Standard Trap vs. Straight Pressure); ``None`` keeps the Standard default."""
    targets = (
        play.defense_targets(bh_xy, def_coords, is_away_offense, off_coords)
        if play is not None
        else _defense_targets(bh_xy, def_coords, is_away_offense, off_coords)
    )
    for pos, tgt in targets.items():
        def_coords[pos] = dict(tgt)


def _move_defense(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    seconds: float,
    def_lineup: Dict[str, Any],
    off_coords: Optional[Dict[str, Dict[str, int]]] = None,
    play: Any = None,
) -> None:
    """D15: move each defender toward its §6 target at the player's rate,
    **interrupted** by the segment duration, tracking actual positions.

    Backcourt defenders use the *standard* archetype; the **PF/C use sprint**
    (D22 — they cover ground to their ball-reactive coverage spots). A quicker
    ball handler still gains real separation (the defense no longer teleports
    back onto him every step). Matches the emitter's interrupted-coord render.
    Mutates ``def_coords`` in place. ``off_coords`` feeds the D22 PF/C coverage.
    ``play`` selects the formation seam (Standard vs. Straight Pressure).
    """
    targets = (
        play.defense_targets(bh_xy, def_coords, is_away_offense, off_coords)
        if play is not None
        else _defense_targets(bh_xy, def_coords, is_away_offense, off_coords)
    )
    for pos in POSITIONS:
        arch = "sprint" if pos in ("PF", "C") else "standard"
        rate = _ag_grid_per_game_sec(def_lineup.get(pos), arch)
        if rate <= 0:
            def_coords[pos] = _clamp_xy(targets[pos])
            continue
        def_coords[pos] = _clamp_xy(
            _interrupted_coord(def_coords[pos], targets[pos], rate, seconds)
        )


def _prior_final_coords(game: Any) -> Dict[str, Dict[str, Any]]:
    """The prior turn's per-player final (BIP-end) coords, keyed by player_id.

    Empty when there is no prior turn (first possession / offline tests), in
    which case the engine assumes off-ball offense have arrived at setup.
    """
    turns = getattr(game, "turns", None) or []
    if not turns:
        return {}
    last = turns[-1]
    return (last.get("final_coords") or {}) if isinstance(last, dict) else {}


def _walk_up_loop_start_offense(
    prior_coords: Dict[str, Dict[str, Any]],
    off_lineup: Dict[str, Any],
    off_targets: Dict[str, Dict[str, int]],
    bh_pos: str,
    bh_target: Dict[str, Any],
) -> Dict[str, Dict[str, int]]:
    """D15b: off-ball offense *actual* positions at the start of the §4 loop.

    They begin the possession at their prior-turn final coords and hustle toward
    their setup spots at ``sprint`` during the BH-gated walk-up (duration = the
    BH's standard-rate travel to ``bh_target``), so by loop start they may still
    be en route. Mirrors the emitter's ``build_walk_up_step`` so the engine model
    matches the render. Falls back to the setup target (assume arrived) per
    player whenever prior coords are unavailable. The BH is the gate → he reaches
    his setup target, so he always starts the loop arrived.
    """
    coords: Dict[str, Dict[str, int]] = {pos: dict(off_targets[pos]) for pos in POSITIONS}
    if not prior_coords:
        return coords
    bh_player = off_lineup.get(bh_pos)
    bh_prior = prior_coords.get(_player_id(bh_player))
    if not bh_prior:
        return coords
    bh_rate = _ag_grid_per_game_sec(bh_player, "standard")
    walk_t = _euclid(bh_prior, bh_target) / bh_rate if bh_rate > 0 else 0.0
    for pos in POSITIONS:
        if pos == bh_pos:
            continue
        player = off_lineup.get(pos)
        p_prior = prior_coords.get(_player_id(player))
        if not p_prior:
            continue
        rate = _ag_grid_per_game_sec(player, "sprint")
        if rate <= 0:
            continue
        coords[pos] = _clamp_xy(
            _interrupted_coord(p_prior, off_targets[pos], rate, walk_t)
        )
    return coords


def _move_offense(
    off_coords: Dict[str, Dict[str, int]],
    off_targets: Dict[str, Dict[str, int]],
    seconds: float,
    off_lineup: Dict[str, Any],
    bh_pos: str,
    exclude: Optional[set] = None,
) -> None:
    """D15b: off-ball offense keep hustling toward their setup spots at ``sprint``,
    interrupted by the segment duration, tracking actual positions across
    segments. The ball handler (and any ``exclude`` positions, e.g. a pass
    receiver mid-catch) are moved by the segment logic, not here. Mutates
    ``off_coords`` in place. Matches the emitter's off-ball interrupted render.
    """
    skip = {bh_pos} | (exclude or set())
    for pos in POSITIONS:
        if pos in skip:
            continue
        rate = _ag_grid_per_game_sec(off_lineup.get(pos), "sprint")
        if rate <= 0:
            continue
        off_coords[pos] = _clamp_xy(
            _interrupted_coord(off_coords[pos], off_targets[pos], rate, seconds)
        )


def _segment(
    reason: str,
    off_coords: Dict[str, Dict[str, int]],
    def_coords: Dict[str, Dict[str, int]],
    seconds: float,
    gate: Tuple[str, str],
    ball_owner_pos: str = "PG",
    label: str = "",
) -> Dict[str, Any]:
    """Snapshot a loop segment's per-player end coords + gate.

    ``gate`` is ``(side, pos)`` where side ∈ {"off", "def"} — the player whose
    arrival ends the step. ``ball_owner_pos`` is the offensive position holding
    the ball at the end of the segment (changes after a pass). ``label`` is a
    human-readable step description for the per-step coord trace log.
    """
    return {
        "reason": reason,
        "step_label": label or reason,
        "off_end": {p: dict(off_coords[p]) for p in POSITIONS},
        "def_end": {p: dict(def_coords[p]) for p in POSITIONS},
        "seconds": round(float(seconds), 2),
        "gate": list(gate),
        "ball_owner_pos": ball_owner_pos,
    }


def _pass_segment(
    passer_pos: str,
    receiver_pos: str,
    off_coords: Dict[str, Dict[str, int]],
    def_coords: Dict[str, Dict[str, int]],
    seconds: float,
    label: str = "pass",
) -> Dict[str, Any]:
    """A ball-in-flight segment (§6 pass). Offense holds while the ball travels
    passer → receiver; the defense moves to ``def_coords``. The emitter renders
    this via the universal ``build_pass_step`` primitive (ball flight + SFX).
    Ball ownership transitions to the receiver at the end of the segment.
    """
    seg = _segment(
        "hct_pass", off_coords, def_coords, seconds, ("off", receiver_pos),
        ball_owner_pos=receiver_pos, label=label,
    )
    seg["pass_from_pos"] = passer_pos
    seg["pass_to_pos"] = receiver_pos
    return seg


def _resolve_hct_pass_contest(
    off_team: Any,
    passer: Any,
    passer_xy: Dict[str, Any],
    receiver_xy: Dict[str, Any],
    def_lineup: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
) -> Dict[str, Any]:
    """§14 — resolve the HCT outlet pass contest. Builds the passer + the
    eligible defender descriptors from live coords/attributes and the HCT offense
    modifier (``pt_opp_modifier``), then delegates to the pure
    ``resolve_pass_contest``. Returns ``{outcome, deflector, contact_point}``
    (deflector is a def position key).

    §14 rule — **the defender(s) guarding the passer cannot intercept his own
    outlet.** In a trap two men are committed on the ball (a single in pressure);
    they're engaging the passer, not sitting in the passing lane, so they're
    removed from the interceptor pool. "Guarding" = within ``MOMENT_RANGE`` of the
    passer (the same range that defines the pressure/trap moment)."""
    p_attrs = getattr(passer, "attributes", None) or {}
    passer_desc = {
        "xy": passer_xy,
        "PS": p_attrs.get("PS", 50),
        "CH": p_attrs.get("CH", 50),
        "IQ": p_attrs.get("IQ", 50),
    }
    # On-ball defenders (trappers / pressure man) are ineligible to pick off the
    # pass they're contesting.
    guarding = set(_in_range_defenders(passer_xy, def_coords))
    defenders: List[Dict[str, Any]] = []
    for pos in POSITIONS:
        if pos in guarding:
            continue
        d = def_lineup.get(pos)
        if d is None:
            continue
        d_attrs = getattr(d, "attributes", None) or {}
        defenders.append(
            {
                "id": pos,
                "xy": def_coords[pos],
                "rate": ag_to_grid_per_game_sec(d_attrs.get("AG", 50)),
                "OD": d_attrs.get("OD", 50),
                "CH": d_attrs.get("CH", 50),
                "IQ": d_attrs.get("IQ", 50),
            }
        )
    offense_modifier = resolve_offense_pass_modifier(
        "HCT", getattr(off_team, "team_attributes", None)
    )
    return resolve_pass_contest(
        passer_desc,
        receiver_xy,
        PASS_GRID_PER_GAME_SEC,
        defenders,
        offense_modifier=offense_modifier,
    )


def _emit_dead_ball_drive(
    bh_xy, score_ratio, is_away_offense, bh_drive_rate, off_coords, def_coords, bh_pos,
    play: Any = None,
) -> Tuple[Dict[str, Any], float]:
    """BH drives partway toward the deep key, then commits a dead-ball turnover.
    Mutates ``off_coords``/``def_coords`` and returns ``(segment, seconds)``.
    ``play`` selects the defensive formation seam."""
    deep_key = DEEP_KEY_SPOT if not is_away_offense else _flip(DEEP_KEY_SPOT)
    path_distance = _euclid(bh_xy, deep_key)
    partial_elapsed = (path_distance * score_ratio) / bh_drive_rate
    attack_xy = _clamp_xy(_move_at_pace(bh_xy, deep_key, partial_elapsed, bh_drive_rate))
    off_coords[bh_pos] = attack_xy
    _position_defense(attack_xy, def_coords, is_away_offense, off_coords, play=play)
    seconds = max(0.3, partial_elapsed)
    return (
        _segment(
            "hct_attack", off_coords, def_coords, seconds, ("off", bh_pos), bh_pos,
            label="attack → forced dead-ball turnover (terminal)",
        ),
        seconds,
    )


def _fcp_ball_handler_pos(game: Any, off_lineup: Dict[str, Any]) -> str:
    """Inbound receiver for FCP — from ``prior_turn.final_ball_handler_id``."""
    turns = getattr(game, "turns", None) or []
    if turns:
        last = turns[-1]
        if isinstance(last, dict):
            bh_id = last.get("final_ball_handler_id")
            if bh_id:
                for pos, player in off_lineup.items():
                    if player is not None and _player_id(player) == bh_id:
                        return pos
    return "PG"


def _seed_lineup_coords_from_prior(
    prior_coords: Dict[str, Dict[str, Any]],
    lineup: Dict[str, Any],
) -> Dict[str, Dict[str, int]]:
    """Map lineup positions → coords from prior-turn finals, else ``player.coords``."""
    coords: Dict[str, Dict[str, int]] = {}
    for pos in POSITIONS:
        player = lineup.get(pos)
        if player is not None:
            pid = _player_id(player)
            if pid and pid in prior_coords:
                coords[pos] = _clamp_xy(prior_coords[pid])
                continue
            raw = getattr(player, "coords", None)
            if raw:
                coords[pos] = _clamp_xy(raw)
                continue
        coords[pos] = {"x": 50, "y": 25}
    return coords


def _backcourt_uncleared_for_ten_second(
    bh_xy: Dict[str, Any], is_away_offense: bool, turn_mode: str
) -> bool:
    """True while the BH has not cleared the backcourt clock boundary."""
    if turn_mode == "fcp":
        return not _past_primary_safe_area(bh_xy, is_away_offense)
    return not _crossed_half_court(bh_xy["x"], is_away_offense)


def _sf_at_fcp_inbound_spot(
    off_coords: Dict[str, Dict[str, int]], is_away_offense: bool
) -> bool:
    sf = off_coords.get("SF") or {}
    x = float(sf.get("x", 50))
    if is_away_offense:
        return x >= (100 - FCP_INBOUND_BASELINE_X_HOME)
    return x <= FCP_INBOUND_BASELINE_X_HOME


def compute_dynamic_hct_turn(
    game, play: Any = None, *, turn_mode: str = "hct"
) -> Dict[str, Any]:
    """
    Build the dynamic HCT (or FCP when ``turn_mode="fcp"``) turn for this engine.

    ``play`` is the selected ``HCTPlay`` / ``FCPPlay`` that supplies the
    play-specific seams (``detect_moment`` / ``defense_targets``). When ``None``
    we resolve from ``game_state["hct_trap_play"]`` or ``fcp_press_play``.

    Returns a dict shaped for ``resolve_half_court_trap_logic`` / the FCP wrapper
    to merge into its existing turn result:
        {
            "animations": [...],          # frontend animation list
            "result_type": "DEAD BALL" | "HCO",
            "ball_handler": Player,
            "defender": Player,
            "time_elapsed": float,        # game-seconds total
            "step_clock_seconds": [...],  # per-step game-seconds
            "text_suffix": str,           # optional flavor text appended to "TRAP!"
        }
    """
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup
    def_lineup = def_team.lineup

    is_away_offense = off_team.team_id == game.away_team.team_id
    game_state = getattr(game, "game_state", {}) or {}
    prior_coords = _prior_final_coords(game)

    if play is None:
        if turn_mode == "fcp":
            from BackEnd.engine.fcp_press_plays import get_fcp_press_play

            play = get_fcp_press_play(game_state.get("fcp_press_play"))
        else:
            from BackEnd.engine.hct_trap_plays import get_hct_trap_play

            play = get_hct_trap_play(game_state.get("hct_trap_play"))

    if turn_mode == "fcp":
        bh_pos = _fcp_ball_handler_pos(game, off_lineup)
    else:
        bh_pos = "PG"

    ball_handler = off_lineup.get(bh_pos)
    defender = def_lineup.get(bh_pos)
    if ball_handler is None or defender is None:
        return {
            "bail": True,
            "result_type": "HCO",
            "ball_handler": ball_handler,
            "defender": defender,
            "text_suffix": "",
            "turn_mode": turn_mode,
        }

    if turn_mode == "fcp":
        off_coords = _seed_lineup_coords_from_prior(prior_coords, off_lineup)
        def_coords = _seed_lineup_coords_from_prior(prior_coords, def_lineup)
        off_targets = {pos: dict(off_coords[pos]) for pos in POSITIONS}
        def_targets = {pos: dict(def_coords[pos]) for pos in POSITIONS}
        bh_target = dict(off_targets[bh_pos])
        walk_up_other_offense_targets = {
            pos: dict(off_targets[pos]) for pos in POSITIONS if pos != bh_pos
        }
    else:
        off_targets, def_targets = _build_step_1_targets(bh_pos, is_away_offense)
        bh_target = off_targets[bh_pos]
        walk_up_other_offense_targets = {
            pos: dict(off_targets[pos]) for pos in POSITIONS if pos != bh_pos
        }
        off_coords = _walk_up_loop_start_offense(
            prior_coords, off_lineup, off_targets, bh_pos, bh_target
        )
        def_coords = {
            pos: {"x": int(def_targets[pos]["x"]), "y": int(def_targets[pos]["y"])}
            for pos in POSITIONS
        }

    pg_def = def_lineup.get("PG")

    # AG-driven drive rate. At AG=50 this resolves to 16×0.75 = 12, matching the
    # legacy ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND.
    bh_attrs = getattr(ball_handler, "attributes", None) or {}
    bh_drive_rate = ag_to_grid_per_game_sec(bh_attrs.get("AG", 50))

    bh_xy = off_coords[bh_pos]

    # Seed the running shot clock once (§4 Time terminals). Decremented per
    # segment so the loop is strictly bounded.
    shot_clock = float(game_state.get("shot_clock_remaining", 30) or 30)
    # 10-second rule is measured against ACTUAL elapsed time from possession start
    # (not an absolute shot-clock threshold), and is disabled when the quarter has
    # less than the limit remaining (the period buzzer ends it first).
    shot_clock_start = shot_clock
    quarter_remaining_start = float(
        game_state.get("time_remaining", shot_clock) or shot_clock
    )

    loop_segments: List[Dict[str, Any]] = []
    result_type = "HCO"
    text_suffix = ""
    # Violation subtype for a DEAD BALL terminal (D9 announce / classification):
    # "SHOT_CLOCK" (clock hit 0) or "TEN_SECOND" (didn't cross half court in
    # time). Empty for a defense-forced dead ball (FE renders a generic
    # travel/double-dribble) and for non-turnover outcomes.
    turnover_type = ""
    # D8 — set for the emergent foul/steal terminals. ``foul_team`` is
    # "OFFENSE" (charge) or "DEFENSE" (reach); ``foul_player`` / ``stealer``
    # carry the credited Player so the wrapper can record stats + route.
    foul_team: str = ""
    foul_player: Any = None
    stealer: Any = None
    # On-court location where a STEAL changed hands (the BH's spot) — seeds the
    # stealer's start for the next possession's Steal HCO / fast-break setup.
    steal_coords: Dict[str, Any] = {}
    # §14 — set when the STEAL terminal is a PASS interception (vs a reach-in /
    # strip). Threads through the wrapper to the turn dict so the FE shows the
    # "INTERCEPTION!" announce + interception SFX (gameAnnouncements.isPassInterception).
    is_interception: bool = False
    # §5 — set when a defensive (D_FOUL) terminal is credited to the on-ball
    # defender (a true reach-in). Threads to the turn dict so the FE announces
    # "Reaching In!" rather than the generic off-ball defensive-foul language.
    reach_in_foul: bool = False
    # §14 — set when a pass is batted out of bounds: a DEAD BALL where the OFFENSE
    # RETAINS (side inbound, no flip, no TO) — matches Rim Runner. Threads to the
    # turn dict so the FE announces "Batted Ball Out Of Bounds!" (not a turnover).
    bat_oob: bool = False
    # §14.7 — bat-OOB deflection geometry threaded to the FE so the schema-playback
    # hook (AnimationEngine._runHctBatOobBallSend) can fly the ball passer→contact
    # →nearest sideline (reusing Rim Runner's imperative OOB ball-send). Grid coords
    # of the pickoff point + the deflecting defender position.
    bat_oob_contact: Dict[str, Any] = {}
    bat_oob_deflector_pos: Any = None
    # Reach-in micro-movement (render-space only): the on-ball defender position
    # of the contest moment currently being resolved. Set by ``_resolve_attack``;
    # consumed by ``_stamp_reach_in`` to tag the moment's emitted segment so the
    # FE renders a defender reach-in on EVERY pressure/trap contest (any
    # outcome). Never affects gameplay coords. See Flourish in
    # animation_step_schema.py.
    pending_reach_in_def_pos: Optional[str] = None
    # §5 — the trapper (player) of the contest moment currently being resolved, set
    # by ``_resolve_attack`` so a D_FOUL's 30% backcourt-help bucket can prefer the
    # trapper (the most likely teammate to commit a compensating foul). ``None`` on
    # single-defender pressure / broken-HCT cutoff moments.
    pending_dfoul_trapper: Any = None
    # Set when a broken-HCT attack reaches the topLane spot → D18 fast break.
    # Carries the post-drive offense/defense coords for the shot resolver.
    fb_seed: Dict[str, Any] = {}
    # Set when the BH reaches the Attack Basket Area and a shot is chosen (§7).
    # Carries the offense/defense coords for the in-Attack-Basket shot resolver.
    ab_seed: Dict[str, Any] = {}
    # D21 dribble-dead state: False once the BH gathers his dribble on a
    # broken-HCT cutoff win → reads collapse to pass/hold, no drive. Resets to
    # True whenever a pass transfers the ball to a new BH (and at turn end).
    dribble_alive = True

    # --- FCP engagement: aggression-driven BH ↔ def PG meet (§FCP) ------------
    if turn_mode == "fcp":
        eng_seconds, eng_gate, eng_label = _apply_fcp_engagement(
            off_coords,
            def_coords,
            bh_pos,
            off_lineup,
            def_lineup,
            off_team,
            def_team,
        )
        bh_xy = off_coords[bh_pos]
        _move_offense(off_coords, off_targets, eng_seconds, off_lineup, bh_pos)
        loop_segments.append(
            _segment(
                "fcp_engagement",
                off_coords,
                def_coords,
                eng_seconds,
                eng_gate,
                bh_pos,
                label=eng_label,
            )
        )
        shot_clock -= eng_seconds

    # --- Initial converge: position the defense around the BH (§6) -----------
    # Initialize per-possession play state (man assignments / roles for plays that
    # track them, e.g. Straight Pressure; Standard Trap returns ``self`` unchanged).
    play = play.begin_possession(bh_xy, def_coords, off_coords, is_away_offense)
    pg_initial = dict(def_coords["PG"])
    _position_defense(bh_xy, def_coords, is_away_offense, off_coords, play=play)
    converge_seconds = max(
        0.4,
        calc_ag_segment_seconds(pg_initial, def_coords["PG"], pg_def, archetype="standard"),
    )
    # D15b: off-ball offense keep hustling toward setup during the converge beat.
    _move_offense(off_coords, off_targets, converge_seconds, off_lineup, bh_pos)
    loop_segments.append(
        _segment(
            "hct_converge", off_coords, def_coords, converge_seconds, ("def", "PG"), bh_pos,
            label="converge (defense closes on the BH)",
        )
    )
    shot_clock -= converge_seconds

    def _advance(label: str = "advance (BH dribbles forward)") -> None:
        """Neutral / beaten-pressure advance: BH dribbles forward, defense re-poses."""
        nonlocal bh_xy
        adv_x = bh_xy["x"] + _basket_dir(is_away_offense) * random.randint(
            ADVANCE_X_MIN, ADVANCE_X_MAX
        )
        adv_y = bh_xy["y"] + random.randint(ADVANCE_Y_MIN, ADVANCE_Y_MAX)
        new_bh = _clamp_xy({"x": adv_x, "y": adv_y})
        advance_seconds = max(0.3, _euclid(bh_xy, new_bh) / bh_drive_rate)
        off_coords[bh_pos] = new_bh
        bh_xy = off_coords[bh_pos]
        # D15: defenders chase at their own rate (interrupted), so a quicker BH
        # gains separation rather than the defense snapping back onto him.
        _move_defense(bh_xy, def_coords, is_away_offense, advance_seconds, def_lineup, off_coords, play=play)
        # D15b: off-ball offense keep hustling toward their setup spots.
        _move_offense(off_coords, off_targets, advance_seconds, off_lineup, bh_pos)
        loop_segments.append(
            _segment(
                "hct_advance", off_coords, def_coords, advance_seconds, ("off", bh_pos), bh_pos,
                label=label,
            )
        )

    def _apply_off_ball_drift(seconds: float, exclude: set) -> None:
        """For every stationary player (not in ``exclude``), roll
        ``HCT_DRIFT_PROBABILITY`` to drift toward the offensive rim at the
        ``"drift"`` archetype rate for ``seconds`` (else hold). Mutates
        ``off_coords`` / ``def_coords`` in place. ``exclude`` holds ``(side, pos)``
        tuples for the players already moving this step."""
        rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
        for side, coords, lineup in (
            ("off", off_coords, off_lineup),
            ("def", def_coords, def_lineup),
        ):
            for pos in POSITIONS:
                if (side, pos) in exclude:
                    continue
                drifted_xy, drifted = drift_or_hold_coord(
                    lineup.get(pos), coords[pos], rim, seconds, HCT_DRIFT_PROBABILITY
                )
                if drifted:
                    coords[pos] = _clamp_xy(drifted_xy)

    def _do_broken_hct_cutoff() -> str:
        """§5 / D21 broken-HCT cutoff race. The BH drives to a y-keyed ABA spot
        (topLane / upper apex / lower apex) vs the single closest defender; the
        other 8 hold (test cut). Returns:
        "FAST_BREAK" / "HCO" (clean arrival → §7 numbers), "TERMINAL" (a
        meet-point foul / dead ball — ``result_type`` already set), or "RETAIN"
        (the BH won the collision and is now dribble-dead → re-read)."""
        nonlocal bh_xy, dribble_alive, result_type, text_suffix, pending_dfoul_trapper
        # Drive target keyed to the BH's current y (home orientation; y bands read
        # the same for away, only x flips via _flip).
        if bh_xy["y"] > BROKEN_HCT_DRIVE_Y_MAX:
            base_target = UPPER_APEX_SPOT
        elif bh_xy["y"] < BROKEN_HCT_DRIVE_Y_MIN:
            base_target = LOWER_APEX_SPOT
        else:
            base_target = TOPLANE_SPOT
        target = _clamp_xy(base_target if not is_away_offense else _flip(base_target))
        cutoff_pos, meet = best_cutoff_on_drive(
            bh_xy, target, bh_drive_rate, def_coords, def_lineup,
            get_defender_rate=lambda d: _ag_grid_per_game_sec(d, "standard"),
            clamp_fn=_clamp_xy,
        )
        cutoff_def = def_lineup.get(cutoff_pos) if cutoff_pos else None

        if meet is None or cutoff_pos is None:
            # No angle → clean drive to the y-keyed ABA spot; nearest trail defender
            # chases (cosmetic — no contest).
            trail_pos = min(POSITIONS, key=lambda p: _euclid(bh_xy, def_coords[p]))
            trail_def = def_lineup.get(trail_pos)
            def_rate = _ag_grid_per_game_sec(trail_def, "standard")
            seconds = max(0.3, _euclid(bh_xy, target) / bh_drive_rate)
            off_coords[bh_pos] = target
            if def_rate > 0:
                def_coords[trail_pos] = _clamp_xy(
                    _interrupted_coord(def_coords[trail_pos], target, def_rate, seconds)
                )
            bh_xy = off_coords[bh_pos]
            # Off-ball players each roll to drift toward the rim or hold.
            _apply_off_ball_drift(seconds, {("off", bh_pos), ("def", trail_pos)})
            loop_segments.append(
                _segment(
                    "hct_attack", off_coords, def_coords, seconds, ("off", bh_pos), bh_pos,
                    label="attack (broken-HCT cutoff drive — clean to ABA spot)",
                )
            )
            nonlocal_shot_clock_dec(seconds)
            # D23: a clean broken-HCT arrival runs the same §2 3-tier ABA read
            # (HCO vs Fast Break) as any other ABA arrival.
            if _aba_hco_or_fb():
                return "HCO"
            _do_fast_break(context="broken-HCT clean arrival")
            return "FAST_BREAK"

        # Angle → the BH and the cutoff defender collide at the meet point.
        seconds = max(0.3, _euclid(bh_xy, meet) / bh_drive_rate)
        off_coords[bh_pos] = meet
        def_coords[cutoff_pos] = dict(meet)
        bh_xy = off_coords[bh_pos]
        # Off-ball players each roll to drift toward the rim or hold.
        _apply_off_ball_drift(seconds, {("off", bh_pos), ("def", cutoff_pos)})
        loop_segments.append(
            _segment(
                "hct_attack", off_coords, def_coords, seconds, ("off", bh_pos), bh_pos,
                label="attack (broken-HCT cutoff drive — meet-point collision)",
            )
        )
        nonlocal_shot_clock_dec(seconds)

        outcome, _ratio, credited = resolve_cutoff_contest(
            off_team, def_team, ball_handler, cutoff_def, exclude_steal=True,
        )
        # Single-defender cutoff collision — no trapper for the D_FOUL help bucket.
        pending_dfoul_trapper = None
        if outcome in ("O_FOUL", "D_FOUL"):
            _apply_moment_outcome(outcome, 1.0, credited, context="broken-HCT cutoff collision")
            return "TERMINAL"
        if outcome == "DEAD BALL":
            sec = _emit_stopper(
                "hct_dead_ball",
                "dead ball (terminal — broken-HCT cutoff collision)",
            )
            nonlocal_shot_clock_dec(sec)
            result_type = "DEAD BALL"
            text_suffix = " — stripped at the point of attack, turnover!"
            return "TERMINAL"
        # POS_O / NEUTRAL → BH beats the defender but has gathered his dribble.
        dribble_alive = False
        return "RETAIN"

    def _seed_fast_break() -> None:
        """Snapshot the post-drive offense/defense coords for the FB resolver."""
        nonlocal fb_seed
        fb_seed = {
            "shooter_pos": bh_pos,
            "off_coords": {p: dict(off_coords[p]) for p in POSITIONS},
            "def_coords": {p: dict(def_coords[p]) for p in POSITIONS},
        }

    def _aba_hco_or_fb() -> bool:
        """§2 3-tier ABA read. Returns True → HCO, False → Fast Break.

        - read > HIGH (200) → the head-count-optimal choice (HCO if def>off,
          else FB; ties → FB).
        - MID (125) < read ≤ HIGH → HCO, unless the OFFENSE is set "aggressive"
          (then FB).
        - read ≤ MID → 50/50 random.
        """
        off_in = _count_in_attack_basket(off_coords, is_away_offense)
        def_in = _count_in_attack_basket(def_coords, is_away_offense)
        hco_is_optimal = def_in > off_in  # ties (offenders ≥ defenders) → FB
        read = _player_read(ball_handler)
        if read > GOAL_ACHIEVEMENT_READ_THRESHOLD:
            return hco_is_optimal
        if read > ABA_READ_MID_THRESHOLD:
            return _aggression_call(off_team) != "aggressive"
        return bool(random.getrandbits(1))

    def _do_fast_break(context: str = "fast break") -> None:
        """§7 unified Fast Break executor (D23 — folds in D18). Snapshots the
        post-drive coords and routes to the FB rim resolver, which drives the
        shooter to the basket and resolves a contested-vs-uncontested attempt
        against the lone closest rim protector.

        Stage 1: solo rim attempt (the proven D18 resolver). The finisher-dish
        / contested-pull-up branches (§7 ``n_ahead > 0`` + cutoff) layer on next.
        """
        nonlocal result_type, text_suffix
        _seed_fast_break()
        result_type = "FAST_BREAK_SHOT"
        text_suffix = " they push it — fast break!"

    def _seed_attack_basket_shot() -> None:
        """Snapshot the offense/defense coords (at the moment the BH reaches the
        Attack Basket Area) for the §7 shot resolver. The resolver applies the
        D5 rim-protection collapse + D6 shot-defender pick on these coords."""
        nonlocal ab_seed
        ab_seed = {
            "shooter_pos": bh_pos,
            "off_coords": {p: dict(off_coords[p]) for p in POSITIONS},
            "def_coords": {p: dict(def_coords[p]) for p in POSITIONS},
        }

    def _resolve_attack(moment: str, in_range: List[str]) -> Tuple[str, float, Any]:
        """Pick the contesting defender(s) per §5 and resolve the banded outcome."""
        nonlocal pending_reach_in_def_pos, pending_dfoul_trapper
        if moment == "trap":
            bh_def_pos, trapper_pos = play.select_trappers(
                in_range, bh_xy, def_coords, is_away_offense
            )
        else:
            bh_def_pos, trapper_pos = in_range[0], None
        # Render-space reach-in: the on-ball defender lunges on this contest
        # moment regardless of outcome (on-ball defender only — the trapper does
        # not reach). Stamped onto the moment's emitted segment by _stamp_reach_in.
        pending_reach_in_def_pos = bh_def_pos
        # §5 — remember the trapper so a D_FOUL prefers him for the 30% help bucket.
        pending_dfoul_trapper = def_lineup.get(trapper_pos) if trapper_pos else None
        return _resolve_moment(
            off_team,
            def_team,
            ball_handler,
            def_lineup.get(bh_def_pos),
            def_lineup.get(trapper_pos) if trapper_pos else None,
        )

    def _stamp_reach_in() -> None:
        """Tag the most recently emitted loop segment with the pending contest's
        on-ball defender so the emitter stamps a render-space ``reach_in``
        flourish (FE-only; never mutates gameplay coords). Call right after the
        segment for a contest moment is appended (terminal stopper, dead-ball
        drive, beaten-pressure advance, or the hold beat). Clears the pending
        marker so it can't leak onto a later, unrelated segment."""
        nonlocal pending_reach_in_def_pos
        if pending_reach_in_def_pos and loop_segments:
            loop_segments[-1]["reach_in_def_pos"] = pending_reach_in_def_pos
        pending_reach_in_def_pos = None

    def _emit_stopper(reason: str, label: str = "") -> float:
        """D8 — terminal whistle/steal beat: the defense collapses onto the BH
        for a short hold. Mutates ``def_coords`` and appends the segment."""
        _position_defense(bh_xy, def_coords, is_away_offense, play=play)
        secs = 0.5
        loop_segments.append(
            _segment(reason, off_coords, def_coords, secs, ("def", "PG"), bh_pos, label=label)
        )
        return secs

    def _apply_moment_outcome(
        outcome: str, score_ratio: float, credited: Any, context: str = "moment"
    ) -> bool:
        """D8 — translate a resolved moment into loop state. Returns ``True`` if
        the outcome is terminal (caller should ``break``), ``False`` if the BH
        retains and the loop should advance/continue. ``context`` labels the
        producing moment (e.g. "single-defender pressure", "two-defender trap")
        for the per-step coord trace."""
        nonlocal result_type, text_suffix, turnover_type
        nonlocal foul_team, foul_player, stealer, steal_coords, reach_in_foul
        if outcome == "STEAL":
            steal_coords = dict(bh_xy)
            sec = _emit_stopper("hct_steal", f"steal (terminal — {context})")
            nonlocal_shot_clock_dec(sec)
            result_type = "STEAL"
            stealer = credited
            text_suffix = " — picked his pocket, steal!"
            return True
        if outcome == "O_FOUL":
            sec = _emit_stopper("hct_foul", f"offensive foul (terminal — {context})")
            nonlocal_shot_clock_dec(sec)
            result_type = "FOUL"
            foul_team = "OFFENSE"
            foul_player = ball_handler
            text_suffix = " — offensive foul on the ball handler!"
            return True
        if outcome == "D_FOUL":
            # §5 — the on-ball defender's blow-by causes the foul, but the whistle
            # spreads: 60% on-ball (reach-in), 30% another backcourt defender
            # (trapper/help), 10% a frontcourt help foul to compensate.
            if getattr(play, "key", "") == STANDARD_DIAMOND:
                backcourt_pos, frontcourt_pos = _diamond_court_split(
                    def_coords, is_away_offense,
                    getattr(play, "center_bc_defender", "PG"),
                )
            else:
                backcourt_pos, frontcourt_pos = HCT_BACKCOURT_POS, HCT_FRONTCOURT_POS
            fouler, is_reach_in = _select_d_foul_fouler(
                credited, def_lineup, trapper=pending_dfoul_trapper,
                backcourt_pos=backcourt_pos, frontcourt_pos=frontcourt_pos,
            )
            reach_in_foul = is_reach_in
            label = "reach-in" if is_reach_in else "off-ball help"
            sec = _emit_stopper("hct_foul", f"defensive {label} foul (terminal — {context})")
            nonlocal_shot_clock_dec(sec)
            result_type = "FOUL"
            foul_team = "DEFENSE"
            foul_player = fouler
            text_suffix = (
                " — reach-in foul on the defense!"
                if is_reach_in
                else " — off-ball foul on the defense!"
            )
            return True
        if outcome == "DEAD BALL":
            seg, sec = _emit_dead_ball_drive(
                bh_xy, score_ratio, is_away_offense, bh_drive_rate,
                off_coords, def_coords, bh_pos, play=play,
            )
            loop_segments.append(seg)
            nonlocal_shot_clock_dec(sec)
            result_type = "DEAD BALL"
            # Forced (defense-induced) dead ball — left untyped so the FE renders
            # its generic travel/double-dribble announce.
            text_suffix = " they force a turnover!"
            return True
        # POS_O / NEUTRAL → not terminal.
        return False

    def nonlocal_shot_clock_dec(amount: float) -> None:
        nonlocal shot_clock
        shot_clock -= amount

    def _park_passer(pos: str) -> None:
        """Freeze a player who just passed at his current spot.

        The off-ball setup pull (`_move_offense`) still aims the *original* BH
        at his x=44 bring-up target (`off_targets[PG]`), so once he gives up the
        ball he'd otherwise be dragged backward across half court. Re-pointing
        his target at his current coords keeps him stationary. First cut: hold in
        place; revisit if the prototype wants him to space into the offense.
        """
        off_targets[pos] = dict(off_coords[pos])

    # --- §4 loop ------------------------------------------------------------
    for _ in range(MAX_LOOP_ITERATIONS):
        # 1) Time terminals (checked at the top of each iteration).
        if shot_clock <= 0:
            # D9 — shot-clock violation: turnover → SIP, possession flips.
            result_type = "DEAD BALL"
            turnover_type = "SHOT_CLOCK"
            text_suffix = " shot clock violation!"
            break
        if (
            quarter_remaining_start >= HCT_TEN_SECOND_LIMIT
            and (shot_clock_start - shot_clock) >= HCT_TEN_SECOND_LIMIT
            and _backcourt_uncleared_for_ten_second(bh_xy, is_away_offense, turn_mode)
        ):
            # D9 — 10-second violation: 10 ACTUAL game-seconds elapsed since
            # possession start without clearing the backcourt boundary (half
            # court for HCT, x=64 for FCP) → turnover → SIP, possession flips.
            result_type = "DEAD BALL"
            turnover_type = "TEN_SECOND"
            text_suffix = " 10-second violation!"
            break

        # 2) Zone precedence (§2 / D21): the Attack Basket Area is the ONLY
        # trap-break zone. Reaching the PSA is no longer a trigger — it just
        # continues the loop (the trap persists).
        if _past_primary_safe_area(bh_xy, is_away_offense):
            if _in_attack_basket_area(bh_xy, is_away_offense):
                # §7 goal achievement (§2 3-tier read): HCO vs Fast Break.
                if _aba_hco_or_fb():
                    result_type = "HCO"
                    text_suffix = " they pull it back out to set up the half court offense"
                    break
                # Fast Break — unified FB executor (D23; folds in D18).
                _do_fast_break(context="ABA goal-achievement")
                break
            # 2D-3: past the PSA but outside the Attack-Basket y-band (a deep
            # corner / baseline-extended spot — not a goal-achievement zone).
            # Instead of force-settling to HCO, fall through to a normal
            # detect → read → act iteration so the BH (or a pass receiver who
            # caught here) keeps working from the corner. Forward progress is
            # guaranteed by the segment emitted below and bounded by the shot
            # clock + MAX_LOOP_ITERATIONS.

        # 3) Detect the moment (§5) and read (reduced thresholds if no defender;
        #    attack tier removed once the BH is dribble-dead, D21). The play seam
        #    classifies the moment (Straight Pressure caps it at "pressure").
        moment, in_range = play.detect_moment(bh_xy, def_coords, is_away_offense)
        decision = _read_decision(
            ball_handler, broken=(moment == "none"), dribble_alive=dribble_alive
        )

        if decision == "attack":
            if moment == "none":
                # Broken-HCT cutoff race (D21): drive to topLane vs the closest
                # defender → clean FB/HCO, a meet-point contest, or a retained
                # (now dribble-dead) ball.
                status = _do_broken_hct_cutoff()
                if status == "FAST_BREAK":
                    result_type = "FAST_BREAK_SHOT"
                    text_suffix = " open floor — fast break!"
                    break
                if status == "HCO":
                    result_type = "HCO"
                    text_suffix = " open floor — they break the trap & establish their half court offense"
                    break
                if status == "TERMINAL":
                    break
                continue  # RETAIN → dribble-dead, re-read next iteration
            mlabel = "two-defender trap" if moment == "trap" else "single-defender pressure"
            outcome, score_ratio, credited = _resolve_attack(moment, in_range)
            if _apply_moment_outcome(outcome, score_ratio, credited, context=mlabel):
                _stamp_reach_in()  # tag the terminal stopper/dead-ball segment
                break
            # POS_O / NEUTRAL → advance below.
            _advance(label=f"advance (BH beats the {mlabel})")
            _stamp_reach_in()  # tag the beaten-pressure advance segment
            shot_clock -= loop_segments[-1]["seconds"]
            continue

        if decision == "hold":
            # §5 hold resolution: BH holds the ball for random(1,2)s while the
            # defense keeps closing. Outcome depends on what reaches the BH.
            hold_seconds = float(random.randint(HOLD_SECONDS_MIN, HOLD_SECONDS_MAX))
            # D15: defense keeps closing during the hold at its own rate.
            _move_defense(bh_xy, def_coords, is_away_offense, hold_seconds, def_lineup, off_coords, play=play)
            # D15b: off-ball offense keep hustling toward their setup spots.
            _move_offense(off_coords, off_targets, hold_seconds, off_lineup, bh_pos)
            loop_segments.append(
                _segment(
                    "hct_hold", off_coords, def_coords, hold_seconds, ("off", bh_pos), bh_pos,
                    label="hold (BH holds the ball 1-2s while the defense closes)",
                )
            )
            shot_clock -= hold_seconds

            moment2, in_range2 = play.detect_moment(bh_xy, def_coords, is_away_offense)
            if moment2 == "trap":
                # A second defender arrived during the hold → Trap Moment.
                outcome, score_ratio, credited = _resolve_attack("trap", in_range2)
                if _apply_moment_outcome(
                    outcome, score_ratio, credited, context="two-defender trap (after hold)"
                ):
                    _stamp_reach_in()  # tag the terminal stopper/dead-ball segment
                    break
                _advance(label="advance (BH beats the two-defender trap after hold)")
                _stamp_reach_in()  # tag the beaten-trap advance segment
                shot_clock -= loop_segments[-1]["seconds"]
                continue
            if moment2 == "none":
                # No defender reached the BH before the window elapsed.
                if dribble_alive:
                    # Broken-HCT cutoff race (D21).
                    status = _do_broken_hct_cutoff()
                    if status == "FAST_BREAK":
                        result_type = "FAST_BREAK_SHOT"
                        text_suffix = " open floor — fast break!"
                        break
                    if status == "HCO":
                        result_type = "HCO"
                        text_suffix = " open floor — they break the trap & establish their half court offense"
                        break
                    if status == "TERMINAL":
                        break
                # Dribble-dead (can't drive) or RETAIN → re-read (pass/hold)
                # next iteration; everyone kept moving during the hold beat, so a
                # defender will eventually reach him.
                continue
            # Pressure (single defender reached the holding BH): D8 unifies the
            # hold contest with the attribute-driven moment model (same engine as
            # Attack). Terminal outcomes end the turn; otherwise the BH retains
            # and we re-read next iteration.
            outcome, score_ratio, credited = _resolve_attack("pressure", in_range2)
            terminal = _apply_moment_outcome(
                outcome, score_ratio, credited, context="single-defender pressure (after hold)"
            )
            # Terminal → tag the stopper segment; non-terminal (BH retains, no
            # advance segment here) → tag the hold beat so the reach-in renders
            # during the hold the defender pressured.
            _stamp_reach_in()
            if terminal:
                break
            continue

        # decision == "pass" → §6 pass branch. The ball goes to one of the two
        # teammates closest to the BH; the receiver becomes the new ball handler
        # and the loop continues from him (enables a non-PG HCT-end BH → D7).
        pass_exclude: Optional[set] = None
        if turn_mode == "fcp" and _sf_at_fcp_inbound_spot(off_coords, is_away_offense):
            pass_exclude = {"SF"}
        receiver_pos = _select_pass_receiver(
            bh_pos, off_coords, is_away_offense, exclude=pass_exclude
        )
        passer_pos = bh_pos
        # Once he passes, the ex-BH is off-ball — freeze him so the stale x=44
        # setup pull doesn't drag him back across half court.
        _park_passer(passer_pos)

        # §14 — pass contest: a defender sitting in the outlet lane can pick it
        # off. The geometry/attribute primitive returns COMPLETE / INTERCEPT /
        # BAT_OOB. Phase 2 wires INTERCEPT → the (shipped) STEAL terminal; BAT_OOB
        # is treated as a completion for now — its offense-retains out-of-bounds
        # ball animation lands with the §14.7 Phase-4 polish.
        contest = _resolve_hct_pass_contest(
            off_team, ball_handler, off_coords[passer_pos], off_coords[receiver_pos],
            def_lineup, def_coords,
        )
        if contest["outcome"] == INTERCEPT:
            interceptor_pos = contest["deflector"]
            interceptor = def_lineup.get(interceptor_pos)
            contact = contest["contact_point"] or dict(off_coords[receiver_pos])
            # Picked off in flight: the pass never completes. Reuse the STEAL
            # terminal (possession flips, STL credit, fast-break-off-takeaway) and
            # flag it as an interception so the FE swaps the headline + voice. The
            # passer (current ``ball_handler``) eats the turnover; the contact spot
            # seeds the stealer's next possession.
            result_type = "STEAL"
            stealer = interceptor or stealer
            steal_coords = _clamp_xy(dict(contact))
            is_interception = True
            sec = _emit_stopper(
                "hct_interception",
                f"interception (terminal — {passer_pos}\u2192{receiver_pos} "
                f"picked off by {interceptor_pos})",
            )
            shot_clock -= sec
            text_suffix = " — pass picked off, intercepted!"
            break

        if contest["outcome"] == BAT_OOB:
            deflector_pos = contest["deflector"]
            # Knocked out of bounds in flight: a DEAD BALL where the OFFENSE
            # RETAINS (side inbound, no possession flip, no TO) — matches Rim
            # Runner. The bat_oob flag drives the FE "Batted Ball Out Of Bounds!"
            # announce and suppresses the turnover announce.
            result_type = "DEAD BALL"
            bat_oob = True
            steal_coords = {}
            # §14.7 — geometry for the FE imperative ball-send (fly the ball
            # passer→contact→nearest sideline). Fall back to the receiver spot
            # if the contest didn't pin a contact point.
            bat_oob_contact = _clamp_xy(
                dict(contest["contact_point"] or off_coords[receiver_pos])
            )
            bat_oob_deflector_pos = deflector_pos
            sec = _emit_stopper(
                "hct_bat_oob",
                f"pass batted out of bounds ({passer_pos}\u2192{receiver_pos}, "
                f"deflected by {deflector_pos})",
            )
            shot_clock -= sec
            text_suffix = " — batted out of bounds, they keep it!"
            break

        # Pass flight: the ball travels passer→receiver while the defense closes
        # at its OWN rate (rate-limited, NOT snapped) toward its targets anchored
        # on the receiver (the incoming ball). A quicker close reaches the catch;
        # a slow one leaves the receiver open. Off-ball offense keep hustling; the
        # receiver holds to catch.
        pass_seconds = max(
            0.3, _euclid(off_coords[passer_pos], off_coords[receiver_pos]) / PASS_GRID_PER_GAME_SEC
        )
        _move_defense(
            off_coords[receiver_pos], def_coords, is_away_offense, pass_seconds,
            def_lineup, off_coords, play=play,
        )
        _move_offense(
            off_coords, off_targets, pass_seconds, off_lineup, passer_pos,
            exclude={receiver_pos},
        )
        loop_segments.append(
            _pass_segment(
                passer_pos, receiver_pos, off_coords, def_coords, pass_seconds,
                label=f"pass (backcourt outlet {passer_pos}\u2192{receiver_pos})",
            )
        )
        shot_clock -= pass_seconds

        # The receiver becomes the BH with a live dribble (D21); the loop re-reads
        # & reacts at the top next iteration — NO forced reception hold. His §5
        # read decides attack / hold / pass: if no defender is in range he attempts
        # a Trap Break drive to his y-keyed ABA spot (the shared broken-HCT cutoff)
        # and the closest defender races to cut him off — identical to a primary BH.
        bh_pos = receiver_pos
        bh_xy = off_coords[bh_pos]
        ball_handler = off_lineup.get(bh_pos)
        # The new BH drives at HIS OWN AG-rate (the cutoff race + advances now use
        # the receiver's speed, not the original passer's).
        bh_drive_rate = ag_to_grid_per_game_sec(
            (getattr(ball_handler, "attributes", None) or {}).get("AG", 50)
        )
        dribble_alive = True
        continue
    else:
        # Iteration backstop hit without a terminal — settle into HCO.
        result_type = "HCO"
        text_suffix = text_suffix or " they break the trap & establish their half court offense"

    # Engine returns intermediate data only — the emitter assembles the walk-up
    # step plus one schema step per loop segment.
    return {
        "result_type": result_type,
        "turnover_type": turnover_type,
        # D8 — emergent foul/steal participants (empty/None for other terminals).
        "foul_team": foul_team,
        "foul_player": foul_player,
        "stealer": stealer,
        "steal_coords": steal_coords,
        "is_interception": is_interception,
        "reach_in_foul": reach_in_foul,
        "bat_oob": bat_oob,
        "bat_oob_contact": bat_oob_contact,
        "bat_oob_deflector_pos": bat_oob_deflector_pos,
        "ball_handler": ball_handler,
        "defender": defender,
        "text_suffix": text_suffix,
        # Entry walk-up targets (segment 0).
        "bh_pos": bh_pos,
        "bh_target": bh_target,
        "other_offense_targets": walk_up_other_offense_targets,
        "def_initial_targets": def_targets,
        # Variable-length loop segments (converge, advances, attack).
        "loop_segments": loop_segments,
        # Set only for result_type == "FAST_BREAK_SHOT" (§5 broken-HCT → D18).
        "fb_seed": fb_seed,
        # Set only for result_type == "ATTACK_BASKET_SHOT" (§7 in-AB shot tree).
        "ab_seed": ab_seed,
        # FCP: emitter skips step-0 walk-up (loop starts at BIP-end coords).
        "skip_walk_up": turn_mode == "fcp",
        "turn_mode": turn_mode,
    }
