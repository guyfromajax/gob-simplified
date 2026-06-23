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
import random as _random
from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.utils.shared import player_read_raw, defender_pressure_raw, inside_defender_raw
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
SUBTLE_STEP_ELAPSED_BY_TEMPO = {"slow": (4, 5), "normal": (3, 5), "fast": (2, 4)}
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


def _hot_read_types(player, location, read_map):
    """Shot types this player can hot-read FROM this spot (flag true AND positioned in that area)."""
    flags = read_map.get(getattr(player, "player_id", None), {}) or {}
    if is_inside_location(location):
        return ["inside"] if flags.get("inside") else []
    types = []
    if flags.get("attack"):
        types.append("attack")
    if flags.get("outside"):
        types.append("outside")
    return types


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


def _hot_read_branch(bh, bh_pos, bh_location, off_lineup, locations, read_map, off_aggr, rng):
    """Offense won the read: execute a hot read (self first, else closest teammate) or advance."""
    bh_types = _hot_read_types(bh, bh_location, read_map) if bh else []
    teammate_reads = []
    for pos, loc in locations.items():
        if pos == bh_pos:
            continue
        p = off_lineup.get(pos)
        if not p:
            continue
        t = _hot_read_types(p, loc, read_map)
        if t:
            teammate_reads.append((pos, t))

    if not bh_types and not teammate_reads:
        return {"action": ADVANCE}

    execute_pct = 0.50 + _aggr_delta(off_aggr, 0.20, -0.20)  # aggressive 70% / passive 30%
    if rng.random() >= execute_pct:
        return {"action": ADVANCE}

    if bh_types:  # ball handler reads for himself first
        return {"action": HOT_READ_SHOOT, "shooter_pos": bh_pos,
                "shot_type": rng.choice(bh_types), "via_pass": False}

    # else closest teammate (tie → random)
    dists = [(pos, _dist(bh_location, locations.get(pos, "key"))) for pos, _t in teammate_reads]
    min_d = min(d for _, d in dists)
    closest = [pos for pos, d in dists if abs(d - min_d) < 1e-9]
    chosen_pos = rng.choice(closest)
    types = dict(teammate_reads)[chosen_pos]
    return {"action": HOT_READ_SHOOT, "shooter_pos": chosen_pos,
            "shot_type": rng.choice(types), "via_pass": True}


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
# entry point
# --------------------------------------------------------------------------- #
def decide_step_action(game, step, bh_pos, bh_defender, off_lineup, read_map, rng=_random):
    """
    Decide the ball handler's action for one motion skeleton step (brief Step 2).

    Args:
        game: GameManager (offense_team/defense_team team_attributes + aggression_call; game_state).
        step: the skeleton step dict (pos_actions give each player's location this step).
        bh_pos: ball-handler position key (e.g. "PG").
        bh_defender: the ball handler's defender Player (man matchup, or nearest zone defender —
            resolved by the caller in Phase 3). May be None (treated as no defensive pressure).
        off_lineup: {pos: Player} for the offense.
        read_map: Phase-1 {player_id: {inside,attack,outside}} flags.
        rng: random source (injectable for tests).

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

    # offense_score (form B)
    offense_score = (player_read_raw(bh) + discipline) * rng.randint(1, 6)

    # shot-clock desperation pre-check (only when offense isn't reading well)
    if offense_score < DESPERATION_OFFENSE_CEILING:
        roll = rng.randint(1, 100) + TEMPO_MOD.get(tempo, 0)
        if roll > 4 * shot_clock:
            return _forced_action(bh, bh_pos, bh_location, bh_at_inside, off_lineup, locations, rng)
        # else fall through to the progression point

    # progression point: defense_score (form B)
    if bh_defender is None:
        raw_def = 0.0
    elif bh_at_inside:
        raw_def = inside_defender_raw(bh_defender)
    else:
        raw_def = defender_pressure_raw(bh_defender, defense_playcall)
    defense_score = (raw_def + fight) * rng.randint(1, 6)

    if offense_score > defense_score + def_eff + def_chem:
        return _hot_read_branch(bh, bh_pos, bh_location, off_lineup, locations, read_map, off_aggr, rng)
    if defense_score > offense_score + off_eff + off_chem:
        return _disruption_branch(def_aggr, rng)
    return _neutral_branch(off_aggr, def_aggr, rng)
