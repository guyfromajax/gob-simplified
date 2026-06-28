"""
Dynamic HCO Motion — per-step decision engine (brief Step 2).

Pure decision logic: given the current skeleton step, the ball handler + his
defender, the read map (Phase 1), and team/aggression context, decide what the
ball handler does this step. Returns a Decision dict describing the action —
it does NOT emit any UESS/skeleton steps (that is Phase 3+). See
_documentation_master/projects/Dynamic_HCO_Motion_Brief.md (Step 2).

Scores use brief "form B": (raw_helper + team_modifier) * random.randint(1,6) —
a single roll, with the raw (roll-free) helper variants from BackEnd.utils.shared
so there is no double random.
"""
import logging
import random as _random
from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.utils.shared import (
    player_read_raw, defender_pressure_raw, inside_defender_raw, ball_handling_raw,
)
from BackEnd.engine.motion_read_map import is_inside_location

# --- action vocabulary (Decision["action"]) ---
ADVANCE = "ADVANCE"                  # do nothing this step → next skeleton step
SHOOT = "SHOOT"                      # ball handler shoots (desperation / no-kickout fallback)
KICKOUT_SHOOT = "KICKOUT_SHOOT"      # desperation kick-out → receiver catch-and-shoot
HOT_READ_SHOOT = "HOT_READ_SHOOT"    # hot read executed → shooter shoots (self or via pass)
SUBTLE_MOVEMENT = "SUBTLE_MOVEMENT"
FREELANCE_FORCED = "FREELANCE_FORCED"
PASS_IMMEDIATE = "PASS_IMMEDIATE"

# --- tunables (brief) ---
# Single shared read threshold (brief: "one constant"): a `(read_raw + team_eff) * d6` read
# clears it when > MOTION_READ_THRESHOLD. Used by the desperation ceiling, the per-teammate
# offense subtle read (motion_subtle), and the per-defender subtle read.
MOTION_READ_THRESHOLD = 110
DESPERATION_OFFENSE_CEILING = MOTION_READ_THRESHOLD  # offense_score below this triggers the shot-clock pre-check
KICKOUT_MAX_DIST = 10                # euclidean grid spots for the 25% desperation kick-out
TEMPO_MOD = {"slow": -25, "normal": 0, "fast": 25}
# Subtle-movement step elapsed (game seconds) by offense tempo — a FLOOR the emitter honors
# (brief: Updated Subtle Movement Logic). The slowest mover's natural travel can exceed it.
SUBTLE_STEP_ELAPSED_BY_TEMPO = {"slow": (3, 4), "normal": (2, 4), "fast": (2, 3)}
# Hard penalty applied to shot_score when the BH is forced to shoot because a subtle step
# ran the shot clock to expiry (brief: force a shot with 1s left, -50 to shot score).
SUBTLE_FORCED_SHOT_PENALTY = 50


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _coords(location):
    c = HCO_STRING_SPOTS.get(location) or {"x": 50.0, "y": 25.0}
    return float(c.get("x", 50.0)), float(c.get("y", 25.0))


def _dist(loc_a, loc_b):
    ax, ay = _coords(loc_a)
    bx, by = _coords(loc_b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _aggr_delta(call, aggressive_delta, passive_delta):
    """Return the aggressive/passive adjustment for an aggression_call (0.0 for normal)."""
    if call == "aggressive":
        return aggressive_delta
    if call == "passive":
        return passive_delta
    return 0.0


def _team_attr(team, key, default):
    return (getattr(team, "team_attributes", {}) or {}).get(key, default)


def _aggr_call(team):
    return (getattr(team, "strategy_calls", {}) or {}).get("aggression_call", "normal")


def _step_locations(step):
    out = {}
    for pos, info in (step.get("pos_actions") or {}).items():
        loc = (info or {}).get("location")
        if loc:
            out[pos] = loc
    return out


def _choose_attack_or_outside(player, rng):
    """Brief: attack_score=(AG+SC)/2, outside_score=SH; roll in [1,sum] picks attack vs outside."""
    a = getattr(player, "attributes", {}) or {}
    attack_score = (a.get("AG", 0) + a.get("SC", 0)) / 2
    outside_score = a.get("SH", 0)
    total = attack_score + outside_score
    if total <= 0:
        return "outside"
    shot_roll = rng.randint(1, int(round(total)))
    return "attack" if shot_roll <= attack_score else "outside"


def _shot_type_for_location(player, location, rng):
    if is_inside_location(location):
        return "inside"
    return _choose_attack_or_outside(player, rng)


# --------------------------------------------------------------------------- #
# branches
# --------------------------------------------------------------------------- #
def _forced_action(bh, bh_pos, bh_location, bh_at_inside, off_lineup, locations, rng):
    """Shot-clock desperation: 75% bh shot / 25% kick-out catch-and-shoot."""
    if rng.random() < 0.75:
        shot_type = "inside" if bh_at_inside else _choose_attack_or_outside(bh, rng)
        return {"action": SHOOT, "shooter_pos": bh_pos, "shot_type": shot_type}

    candidates = [
        pos for pos, loc in locations.items()
        if pos != bh_pos and off_lineup.get(pos) is not None
        and _dist(bh_location, loc) <= KICKOUT_MAX_DIST
    ]
    if candidates:
        rpos = rng.choice(candidates)
        receiver = off_lineup.get(rpos)
        rloc = locations.get(rpos, "key")
        return {"action": KICKOUT_SHOOT, "shooter_pos": rpos,
                "shot_type": _shot_type_for_location(receiver, rloc, rng)}
    # no teammate within range → bh shoots himself
    shot_type = "inside" if bh_at_inside else _choose_attack_or_outside(bh, rng)
    return {"action": SHOOT, "shooter_pos": bh_pos, "shot_type": shot_type}


def _disruption_branch(def_aggr, rng):
    """Defense won the read: 50% subtle / 20% Freelance Forced / 30% none (def-aggr adjusts FF/none)."""
    ff = 0.20 + _aggr_delta(def_aggr, 0.10, -0.10)
    none = 0.30 + _aggr_delta(def_aggr, -0.10, 0.10)
    r = rng.random()
    subtle = 1.0 - ff - none  # stays 0.50
    if r < subtle:
        return {"action": SUBTLE_MOVEMENT}
    if r < subtle + ff:
        return {"action": FREELANCE_FORCED}
    return {"action": ADVANCE}  # no effect


def _neutral_branch(off_aggr, def_aggr, rng):
    """Neither side decisively won: 50/50 subtle vs pass, adjusted by both teams' aggression."""
    pass_pct = 0.50 + _aggr_delta(off_aggr, 0.20, -0.20) + _aggr_delta(def_aggr, -0.20, 0.20)
    pass_pct = max(0.10, min(0.90, pass_pct))  # brief: can build to 90/10
    if rng.random() < pass_pct:
        return {"action": PASS_IMMEDIATE}
    return {"action": SUBTLE_MOVEMENT}


# --------------------------------------------------------------------------- #
# Universal Shoot Decision (brief: Proposed: Universal Shoot Decision)
#
# One shared decision evaluated at every BH step, after every subtle beat, and at every
# reception. Two steps: (1) is the look optimal? (shot-type mismatch + openness vs a clock/
# tempo-scaled bar) then (2) does the shooter make the right call? (read tier). Shares the
# read map's raw mismatch scores with the (now label-only) hot read — one computation.
# --------------------------------------------------------------------------- #
SHOT_CLOCK_START = 30              # clamp ceiling for shot-clock-scaled bars
SHOOT_READ_RIGHT = 200             # read tier: optimal decision (shoot/dish if optimal, else progress)
SHOOT_READ_SAFE = 125              # read tier: safe decision (progress)


# Shot-clock tiers — shared by the random-tier % grid and the SM-precedence grid.
# Boundaries (high→low): Early ≥23, Mid ≥15, Late ≥6, Very late ≥1, Forced <1.
# See Dynamic_HCO_System.md §Tunable Constants.
def _shot_clock_tier(shot_clock):
    c = float(shot_clock or 0)
    if c >= 23:
        return "early"
    if c >= 15:
        return "mid"
    if c >= 6:
        return "late"
    if c >= 1:
        return "very_late"
    return "forced"  # <1s — forced-shot region (handled upstream)


# Optimal-look bar (continuous): bar = clock × steepness × tempo_mult. A look's
# 0–100 mismatch quality must clear the bar to be "optimal" — higher = fewer /
# later shots. Self-shot and hot-read dish share the same steepness; tempo scales
# the bar (slow demands a better look — work the ball; fast shoots sooner).
# Raised 1.6→2.0 to push more HCO shots from the Mid (15-22s) tier into Late
# (6-14s) and cut total FGA. See Dynamic_HCO_System.md §Tunable Constants.
OPTIMAL_BAR_STEEPNESS = 2.0
OPTIMAL_BAR_TEMPO_MULT = {"slow": 1.2, "normal": 1.0, "fast": 0.8}

# Non-strategic ("random") read-tier shoot probability (1–100) by shot-clock tier
# and tempo — a clock+tempo progression (low early, high late) so undisciplined
# possessions stop dumping early shots. Very-late is a flat 95% (clock pressure
# dominates); <1s is the forced-shot backstop upstream.
RANDOM_TIER_SHOOT_PCT = {
    "early":     {"slow": 5,  "normal": 15, "fast": 25},
    "mid":       {"slow": 25, "normal": 35, "fast": 45},
    "late":      {"slow": 48, "normal": 58, "fast": 68},
    "very_late": {"slow": 95, "normal": 95, "fast": 95},
}

# Subtle-movement precedence: per shot-clock tier, the tempos for which subtle
# movement takes precedence over the shoot decision (the offense works the ball
# instead of shooting). Gated upstream by the turn's offense_reads / alterations
# roll — NOT a second alterations roll. Precedence retreats as the clock drains
# and as tempo speeds up. See Dynamic_HCO_System.md §Tunable Constants.
SM_PRECEDENCE_TEMPOS = {
    "early":     ("slow", "normal", "fast"),
    "mid":       ("slow", "normal"),
    "late":      ("slow",),
    "very_late": (),
}


def _weighted_attack_or_outside(player, off_team, rng):
    """Weighted attack-vs-outside pick biased by team emphasis (`strategy_settings` attack/outside,
    0–4, +10 each). A stronger skill / higher emphasis is chosen MORE often, not always."""
    a = getattr(player, "attributes", {}) or {}
    s = getattr(off_team, "strategy_settings", {}) or {}
    attack_score = (a.get("AG", 0) + a.get("SC", 0)) / 2 + s.get("attack", 2) * 10
    outside_score = a.get("SH", 0) + s.get("outside", 2) * 10
    total = attack_score + outside_score
    if total <= 0:
        return "outside"
    return "attack" if rng.randint(1, int(round(total))) <= attack_score else "outside"


def _shoot_threshold(shot_clock, tempo_call):
    """Optimal-look bar = clock × steepness × tempo_mult (continuous). Drops as the
    clock drains; slow tempo raises it (work the ball), fast lowers it (shoot sooner)."""
    clock = max(0.0, min(float(shot_clock or 0), SHOT_CLOCK_START))
    return clock * OPTIMAL_BAR_STEEPNESS * OPTIMAL_BAR_TEMPO_MULT.get(tempo_call, 1.0)


def _shoot_read_tier(shooter, off_team, rng):
    """Decision-quality tier (form B): right (>200) / safe (>125) / non-strategic (else)."""
    read = (player_read_raw(shooter) + _team_attr(off_team, "discipline", 0)) * rng.randint(1, 6)
    if read > SHOOT_READ_RIGHT:
        return "right"
    if read > SHOOT_READ_SAFE:
        return "safe"
    return "random"


def _random_tier_shoot_pct(shot_clock, tempo_call):
    """Shoot probability (1–100) for the non-strategic read tier — clock+tempo
    progression (low early, high late). See RANDOM_TIER_SHOOT_PCT."""
    tier = _shot_clock_tier(shot_clock)
    if tier == "forced":
        tier = "very_late"  # <1s forced-shot region — fall to the very-late floor
    tempo = tempo_call if tempo_call in ("slow", "normal", "fast") else "normal"
    return RANDOM_TIER_SHOOT_PCT[tier][tempo]


def sm_takes_precedence(shot_clock, tempo_call):
    """True when subtle movement should take precedence over the shoot decision at
    this shot-clock tier + tempo. The caller gates this on the turn's offense_reads
    (alterations) roll — this is NOT a second alterations roll. See SM_PRECEDENCE_TEMPOS."""
    tier = _shot_clock_tier(shot_clock)
    tempo = tempo_call if tempo_call in ("slow", "normal", "fast") else "normal"
    return tempo in SM_PRECEDENCE_TEMPOS.get(tier, ())


def _evaluate_shot(player, location, read_scores, off_team, shot_clock, tempo_call, openness, rng):
    """(shot_type, quality, optimal, is_mismatch) for one candidate shooter at his location."""
    from BackEnd.engine.motion_read_map import READ_THRESHOLD
    scores = read_scores.get(getattr(player, "player_id", None), {}) or {}
    if is_inside_location(location):
        shot_type = "inside"
    else:
        shot_type = _weighted_attack_or_outside(player, off_team, rng)
    raw = float(scores.get(shot_type, 0.0))
    quality = raw + openness
    return shot_type, quality, quality >= _shoot_threshold(shot_clock, tempo_call), raw > READ_THRESHOLD


def should_shoot(shooter_pos, off_lineup, locations, read_scores, off_team,
                 shot_clock, tempo_call, rng, openness=0.0, allow_dish=True,
                 blocked_dish_targets=None):
    """Universal shoot decision. Returns a SHOOT Decision
    ``{action, shooter_pos, shot_type, via_pass, hot_read}`` or ``None`` (progress).

    Step 1 evaluates the shooter's look (and, when ``allow_dish``, teammates — the "best shot
    available" = the collapsed hot read as a *dish*); Step 2 applies the shooter's read tier:
    right → take it if optimal (self or dish) else progress; safe → progress; random → 50/50.
    ``openness`` (>=0) lifts the shooter's quality (e.g. a frozen defender post-subtle). The
    ``hot_read`` flag tags a shot that came off a genuine mismatch (label only). Receptions pass
    ``allow_dish=False`` (no re-dish).

    ``blocked_dish_targets`` (a set of positions) are teammates whose passing lane is covered —
    the hot-read "truly open" gate (see Dynamic_HCO_System.md §4). They're excluded as
    dish candidates: the offense won't dish into a covered lane."""
    shooter = off_lineup.get(shooter_pos)
    if shooter is None:
        return None
    blocked_dish_targets = blocked_dish_targets or set()
    s_type, s_quality, s_optimal, s_mismatch = _evaluate_shot(
        shooter, locations.get(shooter_pos, "key"), read_scores, off_team, shot_clock, tempo_call, openness, rng)
    best = {"pos": shooter_pos, "type": s_type, "quality": s_quality,
            "optimal": s_optimal, "mismatch": s_mismatch, "via_pass": False}
    if allow_dish:
        for pos, p in off_lineup.items():
            if pos == shooter_pos or not p or locations.get(pos) is None:
                continue
            if pos in blocked_dish_targets:
                continue  # covered passing lane → not "truly open" → not a dish candidate
            t, q, opt, mm = _evaluate_shot(p, locations[pos], read_scores, off_team,
                                           shot_clock, tempo_call, 0.0, rng)
            if opt and q > best["quality"]:
                best = {"pos": pos, "type": t, "quality": q, "optimal": opt, "mismatch": mm, "via_pass": True}

    # 🔎 Optimal-bar diagnostic: confirms the new clock×steepness×tempo bar is live.
    logging.warning(
        "🪟 [SHOT-SELECT] clock=%.1f tempo=%s bar=%.1f best_q=%.1f optimal=%s via_pass=%s",
        float(shot_clock or 0), tempo_call, float(_shoot_threshold(shot_clock, tempo_call)),
        float(best["quality"]), best["optimal"], best["via_pass"],
    )

    tier = _shoot_read_tier(shooter, off_team, rng)
    if tier == "safe":
        return None  # pass the look up → progress
    if tier == "right":
        if best["optimal"]:
            return {"action": SHOOT, "shooter_pos": best["pos"], "shot_type": best["type"],
                    "via_pass": best["via_pass"], "hot_read": best["mismatch"]}
        return None  # nothing optimal → progress
    # non-strategic: clock+tempo shoot progression (low early, high late)
    # instead of a flat 50/50, so undisciplined possessions stop dumping early
    # shots. Very-late (1–3s) is ~95% for all tempos; <1s forced upstream.
    if rng.randint(1, 100) <= _random_tier_shoot_pct(shot_clock, tempo_call):
        return {"action": SHOOT, "shooter_pos": shooter_pos, "shot_type": s_type,
                "via_pass": False, "hot_read": False}
    return None


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def decide_step_action(game, step, bh_pos, bh_defender, off_lineup, read_map, rng=_random,
                       offense_reads=True, defense_pressure=True):
    """
    Decide the ball handler's action for one motion skeleton step (brief Step 2 + Turn-Level
    Read Gating). The two booleans are rolled once per turn by the resolver and select which of
    the four condition-matrix branches applies:

      offense_reads=T, defense_pressure=T  → read battle (offense read vs defense): offense wins
          → hot read or (fallback) subtle; defense wins → disruption; neutral → subtle/pass.
      offense_reads=T, defense_pressure=F  → offense unopposed/"successful" → hot read or subtle.
      offense_reads=F, defense_pressure=T  → ball-handling battle (ball_handling vs defense):
          defense wins → disruption; otherwise (offense wins / neutral) → advance.
      (offense_reads=F, defense_pressure=F → the resolver defers to the static skeleton; this
          function isn't called.)

    Args:
        game: GameManager (offense_team/defense_team team_attributes + aggression_call; game_state).
        step: the skeleton step dict (pos_actions give each player's location this step).
        bh_pos: ball-handler position key (e.g. "PG").
        bh_defender: the ball handler's defender Player (man matchup, or nearest zone defender).
            May be None (treated as no defensive pressure).
        off_lineup: {pos: Player} for the offense.
        read_map: Phase-1 {player_id: {inside,attack,outside}} flags.
        rng: random source (injectable for tests).
        offense_reads: turn-level — offense is executing reads this turn.
        defense_pressure: turn-level — defense is executing pressure this turn.

    Returns:
        Decision dict: {"action": <one of the action constants>, ...payload}.
        Shot actions carry shooter_pos + shot_type (and via_pass for hot reads).
    """
    game_state = getattr(game, "game_state", {}) or {}
    off_team = game.offense_team
    def_team = game.defense_team

    bh = off_lineup.get(bh_pos)
    locations = _step_locations(step)
    bh_location = locations.get(bh_pos, "key")
    bh_at_inside = is_inside_location(bh_location)

    discipline = _team_attr(off_team, "discipline", 0)
    fight = _team_attr(def_team, "fight", 0)
    off_eff = _team_attr(off_team, "offensive_efficiency", 0)
    def_eff = _team_attr(def_team, "defensive_efficiency", 0)
    off_chem = _team_attr(off_team, "team_chemistry", 7)
    def_chem = _team_attr(def_team, "team_chemistry", 7)
    off_aggr = _aggr_call(off_team)
    def_aggr = _aggr_call(def_team)
    shot_clock = game_state.get("shot_clock_remaining", 30)
    defense_playcall = game_state.get("defense_playcall")
    tempo = (getattr(off_team, "strategy_calls", {}) or {}).get("tempo_call", "normal")

    # offense_score (form B) — read-based
    offense_score = (player_read_raw(bh) + discipline) * rng.randint(1, 6)

    # shot-clock desperation pre-check (universal shot-clock safety; only bites when the offense
    # isn't reading well and the clock is low).
    if offense_score < DESPERATION_OFFENSE_CEILING:
        roll = rng.randint(1, 100) + TEMPO_MOD.get(tempo, 0)
        if roll > 4 * shot_clock:
            return _forced_action(bh, bh_pos, bh_location, bh_at_inside, off_lineup, locations, rng)
        # else fall through to the condition matrix

    # NOTE: shots (incl. the old hot read, now a label) are handled BEFORE this by
    # ``should_shoot`` in the resolver. This function is the MOVEMENT decision for when the BH
    # progresses (doesn't shoot): subtle / advance / disruption / pass.

    # Condition 2 — offense reading, defense not pressuring: the offense is unopposed → it keeps
    # probing off-pattern (subtle), since it didn't take a shot.
    if offense_reads and not defense_pressure:
        return {"action": SUBTLE_MOVEMENT}

    # Defense IS pressuring (Condition 1 or 3) → defense_score (form B).
    if bh_defender is None:
        raw_def = 0.0
    elif bh_at_inside:
        raw_def = inside_defender_raw(bh_defender)
    else:
        raw_def = defender_pressure_raw(bh_defender, defense_playcall)
    defense_score = (raw_def + fight) * rng.randint(1, 6)

    if offense_reads:
        # Condition 1 — read battle: offense read score vs defense. Offense wins → it keeps the
        # initiative with a subtle probe (the shot was already offered by should_shoot); defense
        # wins → disruption; neutral → subtle/pass.
        if offense_score > defense_score + def_eff + def_chem:
            return {"action": SUBTLE_MOVEMENT}
        if defense_score > offense_score + off_eff + off_chem:
            return _disruption_branch(def_aggr, rng)
        return _neutral_branch(off_aggr, def_aggr, rng)

    # Condition 3 — offense NOT reading, defense pressuring → ball-handling battle (symmetric to
    # defense_score). Defense wins → disruption; offense wins or neutral → advance (the d-foul
    # check on an offense win is deferred per brief).
    ball_handling_score = (ball_handling_raw(bh) + off_eff) * rng.randint(1, 6)
    if defense_score > ball_handling_score + off_eff + off_chem:
        return _disruption_branch(def_aggr, rng)
    return {"action": ADVANCE}
