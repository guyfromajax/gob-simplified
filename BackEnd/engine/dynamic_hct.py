"""
Dynamic HCT (Half Court Trap) turn resolution.

Spec: ``_documentation_master/projects/Dynamic_HCT_Turns.md``.
Build plan: ``_documentation_master/projects/Dynamic_HCT_Cut2_Plan.md``.

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
)
from BackEnd.utils.shared import (
    ag_to_grid_per_game_sec,
    calc_ag_segment_seconds,
    calculate_ball_handling_score,
    calculate_defender_pressure_score,
    clamp_animation_grid_coords,
    get_away_player_coords,
)
from BackEnd.utils.shared_defense import HCT_STANDARD_NORMAL, compute_hct_trap_formation
from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec
from BackEnd.utils.transition_bridge import _interrupted_coord


# 10-second violation gate (per Dynamic_HCT_Turns.md "Special Situations").
# When the shot clock reaches this threshold and the ball handler has not yet
# crossed half-court, we announce "10-Second Violation" and run the standard
# dead-ball-turnover flow → SIP. NOT WIRED in first cut; constant defined now
# so the next iteration can plug in the runtime check without churn.
HCT_SHOT_CLOCK_VIOLATION_THRESHOLD = 20

# Step 1 BH target: x = 44, y random in [21, 29].
STEP_1_BH_TARGET_X = 44
STEP_1_BH_TARGET_Y_MIN = 21
STEP_1_BH_TARGET_Y_MAX = 29

# Step 2 defensive PG converge offset: defender x = BH_x + 2 (toward home basket
# in home-defending orientation), same y as BH.
STEP_2_DEFENDER_X_OFFSET = 2

# Step 3 HCO transition target: BH dribbles to deep key spot.
DEEP_KEY_SPOT = HCO_STRING_SPOTS["deep key"]  # (57, 25)

# Defensive PG's step-1 target (override per spec): exact center court spot.
DEFENSIVE_PG_STEP_1_TARGET = HCO_STRING_SPOTS["center court"]  # (50, 25)

# Pos1-4 geometric ranges (home-on-offense orientation; flipped at runtime when
# away is on offense). Each range is (x_min, x_max, y_min, y_max).
POS_TARGET_RANGES = {
    "pos1": (57, 73, 35, 45),  # upper wing region
    "pos2": (57, 73, 5, 15),   # lower wing region
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

# §5 broken-HCT cutoff target: the open-floor attack drives to the topLane spot
# (inside the Attack Basket Area) vs the closest defender (D21). Reaching it
# clean → §7 FB/HCO.
TOPLANE_SPOT = HCO_STRING_SPOTS["topLane"]  # (74, 25)

# §7 Attack Basket Area (§2): x 64→basket, y 10-40 (the band spans lower wing y
# → upper wing y; corrected from the earlier erroneous 10-30, D22). The sole
# trap-break zone (D21) — the BH attempts a shot / FB or transitions to HCO when
# he reaches it. Effectively x>64 (the x=64 boundary belongs to the PSA band).
ATTACK_BASKET_Y_MIN, ATTACK_BASKET_Y_MAX = 10, 40

# §7 goal-achievement read: read > this → make the optimal choice, else random.
GOAL_ACHIEVEMENT_READ_THRESHOLD = 200

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

# §4 read thresholds (attack / pass; else hold).
READ_ATTACK_THRESHOLD = 200
READ_PASS_THRESHOLD = 120

# §5 broken-HCT (no defender in range) reduced read thresholds.
BROKEN_READ_ATTACK_THRESHOLD = 175
BROKEN_READ_PASS_THRESHOLD = 110

# §4 neutral-advance: BH moves +rand(ADV_X) toward basket, +rand(ADV_Y) in y.
ADVANCE_X_MIN, ADVANCE_X_MAX = 6, 12
ADVANCE_Y_MIN, ADVANCE_Y_MAX = -6, 6

# §5 moment detection: a defender is "in range" within this euclidean distance.
MOMENT_RANGE = 11

# §6 shift triggers (on ball-handler y): y < 20 → lower; y > 30 → upper; else normal.
SHIFT_LOWER_Y = 20
SHIFT_UPPER_Y = 30

# §5 hold resolution: BH holds the ball for random(1, 3) game seconds.
HOLD_SECONDS_MIN, HOLD_SECONDS_MAX = 1, 3

# §6 pass flight speed (grid spots / game-second). Reuses the universal pass
# primitive's reset-inbound rate so HCT pass timing matches other pass steps.
PASS_GRID_PER_GAME_SEC = float(RESET_INBOUND_PASS_GRID_PER_GAME_SECOND)

# Defensive backstop only — the shot-clock terminal is the real loop bound.
MAX_LOOP_ITERATIONS = 15

# --- D8: attribute-driven foul / steal / turnover moment outcomes -----------
# See _documentation_master/projects/Dynamic_HCT_D8_Scoping.md §3. One tunable
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
HCT_D8_DEF_WIN_BASE = 0.35        # base P(any event) when defense fully wins
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


def _clampf(value: float, lo: float, hi: float) -> float:
    """Clamp a float to [lo, hi]."""
    return max(lo, min(hi, value))


def _aggression_call(def_team) -> str:
    """Resolved per-turn defensive aggression call ∈ {passive, normal, aggressive}."""
    calls = getattr(def_team, "strategy_calls", {}) or {}
    call = calls.get("aggression_call", "normal")
    return call if call in HCT_D8_AGG_MULT else "normal"


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

    ``broken=True`` applies the §5 reduced thresholds used when no defender is
    in range (an open floor invites attack). ``dribble_alive=False`` (D21): the
    BH has picked up his dribble, so the **attack tier is removed** — the read
    collapses to pass (> pass threshold) or hold.
    """
    score = _player_read(player)
    attack_t = BROKEN_READ_ATTACK_THRESHOLD if broken else READ_ATTACK_THRESHOLD
    pass_t = BROKEN_READ_PASS_THRESHOLD if broken else READ_PASS_THRESHOLD
    if dribble_alive and score > attack_t:
        return "attack"
    if score > pass_t:
        return "pass"
    return "hold"


def _steal_credit_defender(bh_defender, trapper):
    """Pick which defender is credited for a steal: the one with the higher
    steal composite (OD·0.4 + AG·0.4 + IQ·0.2). For a lone defender, that's him."""
    if trapper is None:
        return bh_defender

    def _steal_score(d):
        a = getattr(d, "attributes", {}) or {}
        return a.get("OD", 0) * 0.4 + a.get("AG", 0) * 0.4 + a.get("IQ", 0) * 0.2

    return trapper if _steal_score(trapper) > _steal_score(bh_defender) else bh_defender


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
    aggression. See ``Dynamic_HCT_D8_Scoping.md`` §3.
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
    # Spec uses ``*``; treat pt_opp == 0 as a no-op multiplier (1) so an unset
    # team attribute doesn't auto-zero the handling score.
    o_score = base_handling * (pt_opp * random.randint(1, 6)) if pt_opp > 0 else base_handling

    agg = HCT_D8_AGG_MULT.get(_aggression_call(def_team), 1.0)
    bh = getattr(ball_handler, "attributes", {}) or {}
    ref = HCT_D8_REF

    # --- Defense wins the moment → STEAL / DEAD BALL / O_FOUL / no-event -----
    if d_score > o_score + 2 * (off_chem + pt_opp):
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
    if o_score >= d_score + 2 * (def_chem + pt_eff):
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
    """BH advanced beyond the PSA band into the deep front court (x>64 home /
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
    pg_in_range: bool,
) -> Tuple[str, str]:
    """§5 trapper selection. Returns ``(bh_defender_pos, trapper_pos)``.

    Defensive PG is always a trapper when in range (the second is the closest
    other in-range defender). Fallback when PG is out of range: the two closest
    in-range defenders. ``in_range`` is nearest-first.
    """
    if pg_in_range and "PG" in in_range:
        others = [p for p in in_range if p != "PG"]
        return "PG", others[0]
    return in_range[0], in_range[1]


def _select_pass_receiver(
    bh_pos: str,
    off_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
) -> str:
    """§6 pass: the ball goes to one of the two teammates closest to the BH
    (chosen at random between those two).

    Over-and-back guard: once the BH has crossed half-court he may not pass to a
    teammate still in the backcourt (x<50 home / x>50 away) without an
    over-and-back violation. For now we *prevent* it — if one of the two closest
    teammates would be a violation and the other would not, the legal teammate
    is chosen. (Detecting an actual over-and-back and processing it as a
    dead-ball turnover is a later item; see the §11 outstanding list.)
    """
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


def _position_defense(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    off_coords: Optional[Dict[str, Dict[str, int]]] = None,
) -> None:
    """Snap the defense onto its §6 targets in place (instantaneous reposition —
    used where the defense is *set* at once, e.g. the pass-defense formation).
    ``off_coords`` feeds the D22 PF/C coverage."""
    for pos, tgt in _defense_targets(bh_xy, def_coords, is_away_offense, off_coords).items():
        def_coords[pos] = dict(tgt)


def _move_defense(
    bh_xy: Dict[str, Any],
    def_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    seconds: float,
    def_lineup: Dict[str, Any],
    off_coords: Optional[Dict[str, Dict[str, int]]] = None,
) -> None:
    """D15: move each defender toward its §6 target at the player's rate,
    **interrupted** by the segment duration, tracking actual positions.

    Backcourt defenders use the *standard* archetype; the **PF/C use sprint**
    (D22 — they cover ground to their ball-reactive coverage spots). A quicker
    ball handler still gains real separation (the defense no longer teleports
    back onto him every step). Matches the emitter's interrupted-coord render.
    Mutates ``def_coords`` in place. ``off_coords`` feeds the D22 PF/C coverage.
    """
    targets = _defense_targets(bh_xy, def_coords, is_away_offense, off_coords)
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
) -> Dict[str, Any]:
    """Snapshot a loop segment's per-player end coords + gate.

    ``gate`` is ``(side, pos)`` where side ∈ {"off", "def"} — the player whose
    arrival ends the step. ``ball_owner_pos`` is the offensive position holding
    the ball at the end of the segment (changes after a pass).
    """
    return {
        "reason": reason,
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
) -> Dict[str, Any]:
    """A ball-in-flight segment (§6 pass). Offense holds while the ball travels
    passer → receiver; the defense moves to ``def_coords``. The emitter renders
    this via the universal ``build_pass_step`` primitive (ball flight + SFX).
    Ball ownership transitions to the receiver at the end of the segment.
    """
    seg = _segment(
        "hct_pass", off_coords, def_coords, seconds, ("off", receiver_pos),
        ball_owner_pos=receiver_pos,
    )
    seg["pass_from_pos"] = passer_pos
    seg["pass_to_pos"] = receiver_pos
    return seg


def _emit_dead_ball_drive(
    bh_xy, score_ratio, is_away_offense, bh_drive_rate, off_coords, def_coords, bh_pos
) -> Tuple[Dict[str, Any], float]:
    """BH drives partway toward the deep key, then commits a dead-ball turnover.
    Mutates ``off_coords``/``def_coords`` and returns ``(segment, seconds)``."""
    deep_key = DEEP_KEY_SPOT if not is_away_offense else _flip(DEEP_KEY_SPOT)
    path_distance = _euclid(bh_xy, deep_key)
    partial_elapsed = (path_distance * score_ratio) / bh_drive_rate
    attack_xy = _clamp_xy(_move_at_pace(bh_xy, deep_key, partial_elapsed, bh_drive_rate))
    off_coords[bh_pos] = attack_xy
    _position_defense(attack_xy, def_coords, is_away_offense, off_coords)
    seconds = max(0.3, partial_elapsed)
    return (
        _segment("hct_attack", off_coords, def_coords, seconds, ("off", bh_pos), bh_pos),
        seconds,
    )


def _cutoff_meet_point(
    mover_start: Dict[str, Any],
    mover_target: Dict[str, Any],
    mover_rate: float,
    defender_xy: Dict[str, Any],
    defender_rate: float,
) -> Optional[Dict[str, int]]:
    """§5 / D21 interception solver. Walk the mover's straight path to its target
    and return the **first** point the defender can reach **no later than** the
    mover (the cutoff / meet point), or ``None`` if the defender has no angle.

    Compares arrival times at each sampled point: ``t_mover = dist_along / rate``
    vs ``t_def = dist(defender, point) / rate``. Speeds come from attributes, so
    a quicker player wins the race.
    """
    if mover_rate <= 0 or defender_rate <= 0:
        return None
    total = _euclid(mover_start, mover_target)
    if total <= 0:
        return None
    steps = max(1, int(round(total)))
    for i in range(steps + 1):
        s = i / steps
        point = _interpolate(mover_start, mover_target, s)
        t_mover = (total * s) / mover_rate
        t_def = _euclid(defender_xy, point) / defender_rate
        if t_def <= t_mover:
            return _clamp_xy(point)
    return None


def compute_dynamic_hct_turn(game) -> Dict[str, Any]:
    """
    Build the dynamic HCT turn for this engine state.

    Returns a dict shaped for ``resolve_half_court_trap_logic`` to merge into
    its existing turn result:
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

    # Per spec K — first cut: BH is always PG (the BIP receiver).
    bh_pos = "PG"
    ball_handler = off_lineup.get(bh_pos)
    defender = def_lineup.get(bh_pos)
    if ball_handler is None or defender is None:
        # Defensive bail; caller will fall back to skeleton behavior if needed.
        # Returning ``bail=True`` keeps the contract simple — the phase
        # resolution wrapper checks this and short-circuits.
        return {
            "bail": True,
            "result_type": "HCO",
            "ball_handler": ball_handler,
            "defender": defender,
            "text_suffix": "",
        }

    off_targets, def_targets = _build_step_1_targets(bh_pos, is_away_offense)
    bh_target = off_targets[bh_pos]

    pg_def = def_lineup.get("PG")

    # AG-driven drive rate. At AG=50 this resolves to 16×0.75 = 12, matching the
    # legacy ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND.
    bh_attrs = getattr(ball_handler, "attributes", None) or {}
    bh_drive_rate = ag_to_grid_per_game_sec(bh_attrs.get("AG", 50))

    # --- Running per-player coords (start of the loop = walk-up end) ----------
    # D15b: off-ball offense start the loop at their *actual* walk-up positions
    # (they may still be hustling up from the backcourt), not snapped to setup —
    # so reads that consult their positions (Attack-Basket count, pass targeting)
    # use real coords. The BH is the walk-up gate, so he starts arrived.
    prior_coords = _prior_final_coords(game)
    off_coords: Dict[str, Dict[str, int]] = _walk_up_loop_start_offense(
        prior_coords, off_lineup, off_targets, bh_pos, bh_target
    )
    def_coords: Dict[str, Dict[str, int]] = {
        pos: {"x": int(def_targets[pos]["x"]), "y": int(def_targets[pos]["y"])}
        for pos in POSITIONS
    }
    bh_xy = off_coords[bh_pos]

    # Seed the running shot clock once (§4 Time terminals). Decremented per
    # segment so the loop is strictly bounded.
    game_state = getattr(game, "game_state", {}) or {}
    shot_clock = float(game_state.get("shot_clock_remaining", 30) or 30)

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

    # --- Initial converge: position the defense around the BH (§6) -----------
    pg_initial = dict(def_coords["PG"])
    _position_defense(bh_xy, def_coords, is_away_offense, off_coords)
    converge_seconds = max(
        0.4,
        calc_ag_segment_seconds(pg_initial, def_coords["PG"], pg_def, archetype="standard"),
    )
    # D15b: off-ball offense keep hustling toward setup during the converge beat.
    _move_offense(off_coords, off_targets, converge_seconds, off_lineup, bh_pos)
    loop_segments.append(
        _segment("hct_converge", off_coords, def_coords, converge_seconds, ("def", "PG"), bh_pos)
    )
    shot_clock -= converge_seconds

    def _advance() -> None:
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
        _move_defense(bh_xy, def_coords, is_away_offense, advance_seconds, def_lineup, off_coords)
        # D15b: off-ball offense keep hustling toward their setup spots.
        _move_offense(off_coords, off_targets, advance_seconds, off_lineup, bh_pos)
        loop_segments.append(
            _segment("hct_advance", off_coords, def_coords, advance_seconds, ("off", bh_pos), bh_pos)
        )

    def _do_broken_hct_cutoff() -> str:
        """§5 / D21 broken-HCT cutoff race. The BH drives to topLane vs the
        single closest defender; the other 8 hold (test cut). Returns:
        "FAST_BREAK" / "HCO" (clean arrival → §7 numbers), "TERMINAL" (a
        meet-point foul / dead ball — ``result_type`` already set), or "RETAIN"
        (the BH won the collision and is now dribble-dead → re-read)."""
        nonlocal bh_xy, dribble_alive, result_type, text_suffix
        target = _clamp_xy(TOPLANE_SPOT if not is_away_offense else _flip(TOPLANE_SPOT))
        cutoff_pos = min(POSITIONS, key=lambda p: _euclid(bh_xy, def_coords[p]))
        cutoff_def = def_lineup.get(cutoff_pos)
        def_rate = _ag_grid_per_game_sec(cutoff_def, "standard")
        meet = _cutoff_meet_point(
            bh_xy, target, bh_drive_rate, def_coords[cutoff_pos], def_rate
        )

        if meet is None:
            # No angle → clean drive to topLane; cutoff defender trails.
            seconds = max(0.3, _euclid(bh_xy, target) / bh_drive_rate)
            off_coords[bh_pos] = target
            if def_rate > 0:
                def_coords[cutoff_pos] = _clamp_xy(
                    _interrupted_coord(def_coords[cutoff_pos], target, def_rate, seconds)
                )
            bh_xy = off_coords[bh_pos]
            loop_segments.append(
                _segment("hct_attack", off_coords, def_coords, seconds, ("off", bh_pos), bh_pos)
            )
            nonlocal_shot_clock_dec(seconds)
            off_in = _count_in_attack_basket(off_coords, is_away_offense)
            def_in = _count_in_attack_basket(def_coords, is_away_offense)
            if def_in <= off_in:
                _seed_fast_break()
                return "FAST_BREAK"
            return "HCO"

        # Angle → the BH and the cutoff defender collide at the meet point.
        seconds = max(0.3, _euclid(bh_xy, meet) / bh_drive_rate)
        off_coords[bh_pos] = meet
        def_coords[cutoff_pos] = dict(meet)
        bh_xy = off_coords[bh_pos]
        loop_segments.append(
            _segment("hct_attack", off_coords, def_coords, seconds, ("off", bh_pos), bh_pos)
        )
        nonlocal_shot_clock_dec(seconds)

        outcome, _ratio, credited = _resolve_moment(
            off_team, def_team, ball_handler, cutoff_def, None, exclude_steal=True,
        )
        if outcome in ("O_FOUL", "D_FOUL"):
            _apply_moment_outcome(outcome, 1.0, credited)
            return "TERMINAL"
        if outcome == "DEAD BALL":
            sec = _emit_stopper("hct_dead_ball")
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
        if moment == "trap":
            bh_def_pos, trapper_pos = _select_trappers(in_range, "PG" in in_range)
        else:
            bh_def_pos, trapper_pos = in_range[0], None
        return _resolve_moment(
            off_team,
            def_team,
            ball_handler,
            def_lineup.get(bh_def_pos),
            def_lineup.get(trapper_pos) if trapper_pos else None,
        )

    def _emit_stopper(reason: str) -> float:
        """D8 — terminal whistle/steal beat: the defense collapses onto the BH
        for a short hold. Mutates ``def_coords`` and appends the segment."""
        _position_defense(bh_xy, def_coords, is_away_offense)
        secs = 0.5
        loop_segments.append(
            _segment(reason, off_coords, def_coords, secs, ("def", "PG"), bh_pos)
        )
        return secs

    def _apply_moment_outcome(
        outcome: str, score_ratio: float, credited: Any
    ) -> bool:
        """D8 — translate a resolved moment into loop state. Returns ``True`` if
        the outcome is terminal (caller should ``break``), ``False`` if the BH
        retains and the loop should advance/continue."""
        nonlocal result_type, text_suffix, turnover_type
        nonlocal foul_team, foul_player, stealer, steal_coords
        if outcome == "STEAL":
            steal_coords = dict(bh_xy)
            sec = _emit_stopper("hct_steal")
            nonlocal_shot_clock_dec(sec)
            result_type = "STEAL"
            stealer = credited
            text_suffix = " — picked his pocket, steal!"
            return True
        if outcome == "O_FOUL":
            sec = _emit_stopper("hct_foul")
            nonlocal_shot_clock_dec(sec)
            result_type = "FOUL"
            foul_team = "OFFENSE"
            foul_player = ball_handler
            text_suffix = " — offensive foul on the ball handler!"
            return True
        if outcome == "D_FOUL":
            sec = _emit_stopper("hct_foul")
            nonlocal_shot_clock_dec(sec)
            result_type = "FOUL"
            foul_team = "DEFENSE"
            foul_player = credited
            text_suffix = " — reach-in foul on the defense!"
            return True
        if outcome == "DEAD BALL":
            seg, sec = _emit_dead_ball_drive(
                bh_xy, score_ratio, is_away_offense, bh_drive_rate,
                off_coords, def_coords, bh_pos,
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
        if shot_clock <= HCT_SHOT_CLOCK_VIOLATION_THRESHOLD and not _crossed_half_court(
            bh_xy["x"], is_away_offense
        ):
            # D9 — 10-second violation: didn't cross half court in time → turnover
            # → SIP, possession flips. Only applies while still in the backcourt.
            result_type = "DEAD BALL"
            turnover_type = "TEN_SECOND"
            text_suffix = " 10-second violation!"
            break

        # 2) Zone precedence (§2 / D21): the Attack Basket Area is the ONLY
        # trap-break zone. Reaching the PSA is no longer a trigger — it just
        # continues the loop (the trap persists).
        if _past_primary_safe_area(bh_xy, is_away_offense):
            if _in_attack_basket_area(bh_xy, is_away_offense):
                # §7 goal achievement: shot attempt vs. HCO, decided by the
                # offender/defender count inside the Attack Basket Area + a read.
                off_in = _count_in_attack_basket(off_coords, is_away_offense)
                def_in = _count_in_attack_basket(def_coords, is_away_offense)
                hco_is_optimal = def_in > off_in  # ties (offenders ≥ defenders) → attack
                read = _player_read(ball_handler)
                if read > GOAL_ACHIEVEMENT_READ_THRESHOLD:
                    go_hco = hco_is_optimal
                else:
                    go_hco = bool(random.getrandbits(1))
                if go_hco:
                    result_type = "HCO"
                    text_suffix = " they pull it back out to set up the half court offense"
                    break
                # Shot attempt — §7 shoot / drive / pass tree.
                attempt = _choose_shot_attempt(ball_handler, bh_xy, def_coords, dribble_alive)
                if attempt == "pass":
                    # §7 top-level pass to a teammate past x=64.
                    receiver_pos = _select_top_level_pass_receiver(
                        bh_pos, off_coords, def_coords, is_away_offense
                    )
                    if receiver_pos is not None:
                        # Once he passes, the ex-BH is off-ball — freeze him so
                        # the stale x=44 setup pull doesn't drag him backward.
                        _park_passer(bh_pos)
                        # Flight: persist the pass-defense formation around the
                        # receiver, then the ball travels (forward pool → no
                        # over-and-back). Receiver becomes the new BH.
                        pass_def_coords = {p: dict(def_coords[p]) for p in POSITIONS}
                        _position_defense(
                            off_coords[receiver_pos], pass_def_coords, is_away_offense,
                            off_coords,
                        )
                        for p in POSITIONS:
                            def_coords[p] = dict(pass_def_coords[p])
                        pass_seconds = max(
                            0.3,
                            _euclid(off_coords[bh_pos], off_coords[receiver_pos])
                            / PASS_GRID_PER_GAME_SEC,
                        )
                        # D15b: off-ball offense keep hustling during the flight;
                        # the receiver holds to catch.
                        _move_offense(
                            off_coords, off_targets, pass_seconds, off_lineup, bh_pos,
                            exclude={receiver_pos},
                        )
                        loop_segments.append(
                            _pass_segment(
                                bh_pos, receiver_pos, off_coords, def_coords, pass_seconds
                            )
                        )
                        shot_clock -= pass_seconds
                        bh_pos = receiver_pos
                        bh_xy = off_coords[bh_pos]
                        ball_handler = off_lineup.get(bh_pos)
                        # D21: the catch transfers the ball → the new BH has a
                        # live dribble again.
                        dribble_alive = True

                        if _in_attack_basket_area(bh_xy, is_away_offense):
                            # Catch inside the Attack Basket Area → act on the
                            # AB offender/defender ratio.
                            off_in2 = _count_in_attack_basket(off_coords, is_away_offense)
                            def_in2 = _count_in_attack_basket(def_coords, is_away_offense)
                            if def_in2 <= off_in2:
                                # Numbers advantage → attack the rim (D18 bridge).
                                _seed_fast_break()
                                result_type = "FAST_BREAK_SHOT"
                                text_suffix = " quick pass inside — they attack the rim!"
                            else:
                                # Outnumbered → hold → HCO (Kick-Out entry: the
                                # receiver is inside the Attack Basket Area).
                                result_type = "HCO"
                                text_suffix = " they kick it back out & set up the half court offense"
                            break
                        # Caught past x=64 but outside the AB band → the receiver
                        # is the new BH; re-enter the loop (settles to HCO today;
                        # the full detect→read re-entry is the 2D-3 item).
                        continue
                    # No forward teammate to receive → fall back to the
                    # offense-optimal solo finish.
                    bh_attrs = getattr(ball_handler, "attributes", {}) or {}
                    attempt = (
                        "drive"
                        if (bh_attrs.get("SC", 0) + bh_attrs.get("AG", 0)) > DRIVE_SCAG_THRESHOLD
                        else "shoot"
                    )
                _seed_attack_basket_shot()
                if attempt == "drive":
                    result_type = "ATTACK_BASKET_DRIVE"
                    text_suffix = " they attack the rim"
                else:
                    result_type = "ATTACK_BASKET_SHOT"
                    text_suffix = " they go to work in the paint"
                break
            # 2D-3: past the PSA but outside the Attack-Basket y-band (a deep
            # corner / baseline-extended spot — not a goal-achievement zone).
            # Instead of force-settling to HCO, fall through to a normal
            # detect → read → act iteration so the BH (or a pass receiver who
            # caught here) keeps working from the corner. Forward progress is
            # guaranteed by the segment emitted below and bounded by the shot
            # clock + MAX_LOOP_ITERATIONS.

        # 3) Detect the moment (§5) and read (reduced thresholds if no defender;
        #    attack tier removed once the BH is dribble-dead, D21).
        moment, in_range = _detect_moment(bh_xy, def_coords, is_away_offense)
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
            outcome, score_ratio, credited = _resolve_attack(moment, in_range)
            if _apply_moment_outcome(outcome, score_ratio, credited):
                break
            # POS_O / NEUTRAL → advance below.
            _advance()
            shot_clock -= loop_segments[-1]["seconds"]
            continue

        if decision == "hold":
            # §5 hold resolution: BH holds the ball for random(1,3)s while the
            # defense keeps closing. Outcome depends on what reaches the BH.
            hold_seconds = float(random.randint(HOLD_SECONDS_MIN, HOLD_SECONDS_MAX))
            # D15: defense keeps closing during the hold at its own rate.
            _move_defense(bh_xy, def_coords, is_away_offense, hold_seconds, def_lineup, off_coords)
            # D15b: off-ball offense keep hustling toward their setup spots.
            _move_offense(off_coords, off_targets, hold_seconds, off_lineup, bh_pos)
            loop_segments.append(
                _segment("hct_hold", off_coords, def_coords, hold_seconds, ("off", bh_pos), bh_pos)
            )
            shot_clock -= hold_seconds

            moment2, in_range2 = _detect_moment(bh_xy, def_coords, is_away_offense)
            if moment2 == "trap":
                # A second defender arrived during the hold → Trap Moment.
                outcome, score_ratio, credited = _resolve_attack("trap", in_range2)
                if _apply_moment_outcome(outcome, score_ratio, credited):
                    break
                _advance()
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
            if _apply_moment_outcome(outcome, score_ratio, credited):
                break
            continue

        # decision == "pass" → §6 pass branch. The ball goes to one of the two
        # teammates closest to the BH; the receiver becomes the new ball handler
        # and the loop continues from him (enables a non-PG HCT-end BH → D7).
        receiver_pos = _select_pass_receiver(bh_pos, off_coords, is_away_offense)
        passer_pos = bh_pos
        # Once he passes, the ex-BH is off-ball — freeze him so the stale x=44
        # setup pull doesn't drag him back across half court.
        _park_passer(passer_pos)

        # D19 — compute the pass-defense formation ONCE (around the receiver) and
        # persist it across the flight + reception segments so defenders don't
        # re-randomize/jitter between the two steps.
        pass_def_coords = {p: dict(def_coords[p]) for p in POSITIONS}
        _position_defense(
            off_coords[receiver_pos], pass_def_coords, is_away_offense, off_coords
        )

        # 1) Flight: offense holds, the persisted defense closes, ball travels.
        for p in POSITIONS:
            def_coords[p] = dict(pass_def_coords[p])
        pass_seconds = max(
            0.3, _euclid(off_coords[passer_pos], off_coords[receiver_pos]) / PASS_GRID_PER_GAME_SEC
        )
        # D15b: off-ball offense keep hustling during the flight; the receiver
        # holds to catch.
        _move_offense(
            off_coords, off_targets, pass_seconds, off_lineup, passer_pos,
            exclude={receiver_pos},
        )
        loop_segments.append(
            _pass_segment(passer_pos, receiver_pos, off_coords, def_coords, pass_seconds)
        )
        shot_clock -= pass_seconds

        # 2) Reception/hold: receiver holds at the catch spot for random(1,3)s;
        #    the persisted defense holds its formation. Receiver is now the BH
        #    with a live dribble again (D21).
        bh_pos = receiver_pos
        bh_xy = off_coords[bh_pos]
        ball_handler = off_lineup.get(bh_pos)
        dribble_alive = True
        recv_hold_seconds = float(random.randint(HOLD_SECONDS_MIN, HOLD_SECONDS_MAX))
        # D15b: off-ball offense keep hustling toward setup during the reception.
        _move_offense(off_coords, off_targets, recv_hold_seconds, off_lineup, bh_pos)
        loop_segments.append(
            _segment(
                "hct_reception", off_coords, def_coords, recv_hold_seconds, ("off", bh_pos), bh_pos
            )
        )
        shot_clock -= recv_hold_seconds
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
        "ball_handler": ball_handler,
        "defender": defender,
        "text_suffix": text_suffix,
        # Entry walk-up targets (segment 0).
        "bh_pos": bh_pos,
        "bh_target": bh_target,
        "other_offense_targets": {
            pos: off_targets[pos] for pos in POSITIONS if pos != bh_pos
        },
        "def_initial_targets": def_targets,
        # Variable-length loop segments (converge, advances, attack).
        "loop_segments": loop_segments,
        # Set only for result_type == "FAST_BREAK_SHOT" (§5 broken-HCT → D18).
        "fb_seed": fb_seed,
        # Set only for result_type == "ATTACK_BASKET_SHOT" (§7 in-AB shot tree).
        "ab_seed": ab_seed,
    }
