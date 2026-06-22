"""
Dynamic HCO Motion — Read Map (brief Steps 0 & 1).

Builds the per-turn, per-offensive-player mismatch map consumed by the Motion
offense decision engine (Step 2). Pure computation: no DB reads, no UESS,
ephemeral (the caller attaches it to the turn context; it is NOT persisted).
See _documentation_master/projects/Dynamic_HCO_Motion_Brief.md.

For each of the five offensive players we flag whether they hold an exploitable
edge for an inside / attack / outside shot (mismatch score > READ_THRESHOLD),
against either their man defender (1:1 matchup) or a zone (team-level zone-area
defensive scores). Man and zone are normalized to the same 0–100 differential
scale, so the single threshold means the same thing for both.
"""
from BackEnd.utils.defense_identity import defense_zone_shell_variant
from BackEnd.utils.defense_utils import is_zone_defense
from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team

# Brief Step 1: a shot-type mismatch score above this flags that shot type as a
# potential read for the player.
READ_THRESHOLD = 15

# Canonical inside spots (brief "Spot Classifications"): both lowPost, both midPost,
# midLane, basketSpot. Everything else (named or grid) is an outside/attack spot.
# Matches phase_resolution._is_inside_location's set; defined here to avoid importing
# from phase_resolution (which would create a cycle once Step 2/3 wire back in).
INSIDE_SPOTS = frozenset({
    "lower lowPost", "upper lowPost",
    "lower midPost", "upper midPost",
    "midLane", "basketSpot",
})


def is_inside_location(location):
    """True if a named location is an inside spot (brief canonical set)."""
    return location in INSIDE_SPOTS

# Per zone shell variant ('23' | '32' | '131'), does each defender position's zone
# area (union of the normal + all shift states) touch any inside spot / any outside
# (= attack) spot? Derived from the `defenses` collection `zone_definitions` in
# gob-staging via scripts/pull_zone_areas.py — inside set = both lowPost, both
# midPost, midLane, basketSpot. Regenerate that script if zone_definitions change.
ZONE_AREA_COVERAGE = {
    "23": {  # 2-3 zone — C sits in the paint, covers inside only
        "PG": {"inside": True,  "outside": True},
        "SG": {"inside": True,  "outside": True},
        "SF": {"inside": True,  "outside": True},
        "PF": {"inside": True,  "outside": True},
        "C":  {"inside": True,  "outside": False},
    },
    "32": {  # 3-2 zone — all five cover both regions across shifts
        "PG": {"inside": True, "outside": True},
        "SG": {"inside": True, "outside": True},
        "SF": {"inside": True, "outside": True},
        "PF": {"inside": True, "outside": True},
        "C":  {"inside": True, "outside": True},
    },
    "131": {  # 1-3-1 zone — all five cover both regions across shifts
        "PG": {"inside": True, "outside": True},
        "SG": {"inside": True, "outside": True},
        "SF": {"inside": True, "outside": True},
        "PF": {"inside": True, "outside": True},
        "C":  {"inside": True, "outside": True},
    },
}

# Defender that has no explicit coverage entry (e.g. unknown variant) is assumed to
# cover both regions, so it counts toward every D-score rather than being dropped.
_DEFAULT_COVERAGE = {"inside": True, "outside": True}


def _attr(player, key):
    """Safe numeric attribute read (0.0 if missing/non-numeric)."""
    try:
        return float((player.attributes or {}).get(key, 0) or 0)
    except Exception:
        return 0.0


def _empty_flags():
    return {"inside": False, "attack": False, "outside": False}


def _man_read_map(off_lineup, def_lineup, game_state, defending_is_user):
    """1:1 matchup mismatch scores. Returns {player_id: {inside,attack,outside}}."""
    matchups = get_matchups_for_defending_team(game_state, defending_is_user)  # {def_pos: off_pos}
    off_to_def = {off_pos: def_pos for def_pos, off_pos in matchups.items()}
    out = {}
    for off_pos, off_player in off_lineup.items():
        if not off_player:
            continue
        flags = _empty_flags()
        defender = def_lineup.get(off_to_def.get(off_pos, off_pos))
        if defender:
            inside = ((_attr(off_player, "SC") + _attr(off_player, "ST"))
                      - (_attr(defender, "ID") + _attr(defender, "ST"))) / 2
            outside = _attr(off_player, "SH") - _attr(defender, "OD")
            attack = ((_attr(off_player, "SC") + _attr(off_player, "AG"))
                      - (_attr(defender, "ID") + _attr(defender, "AG"))) / 2
            flags["inside"] = inside > READ_THRESHOLD
            flags["outside"] = outside > READ_THRESHOLD
            flags["attack"] = attack > READ_THRESHOLD
        out[off_player.player_id] = flags
    return out


def _zone_read_map(off_lineup, def_lineup, variant):
    """Team-level zone-area D-scores vs individual offense scores."""
    coverage = ZONE_AREA_COVERAGE.get(variant, {})

    inside_d_parts, outside_d_parts, attack_d_parts = [], [], []
    for def_pos, defender in def_lineup.items():
        if not defender:
            continue
        cov = coverage.get(def_pos, _DEFAULT_COVERAGE)
        if cov.get("inside"):
            inside_d_parts.append((_attr(defender, "ID") + _attr(defender, "ST")) / 2)
        if cov.get("outside"):
            outside_d_parts.append(_attr(defender, "OD"))
            attack_d_parts.append((_attr(defender, "ID") + _attr(defender, "AG")) / 2)

    inside_d = sum(inside_d_parts) / len(inside_d_parts) if inside_d_parts else 0.0
    outside_d = sum(outside_d_parts) / len(outside_d_parts) if outside_d_parts else 0.0
    attack_d = sum(attack_d_parts) / len(attack_d_parts) if attack_d_parts else 0.0

    out = {}
    for off_pos, off_player in off_lineup.items():
        if not off_player:
            continue
        inside = (_attr(off_player, "SC") + _attr(off_player, "ST")) / 2 - inside_d
        outside = _attr(off_player, "SH") - outside_d
        attack = (_attr(off_player, "SC") + _attr(off_player, "AG")) / 2 - attack_d
        out[off_player.player_id] = {
            "inside": inside > READ_THRESHOLD,
            "outside": outside > READ_THRESHOLD,
            "attack": attack > READ_THRESHOLD,
        }
    return out


def build_motion_read_map(game, off_lineup, def_lineup):
    """
    Brief Steps 0 & 1. Returns {player_id: {"inside":bool, "attack":bool, "outside":bool}}
    for the five offensive players — the potential optimal reads for this HCO turn.

    Ephemeral: the caller attaches the result to the turn context; it is not persisted
    to the team document (it depends on both the 5-man lineup and the current defensive
    playcall, so it is recomputed at the start of each HCO turn).
    """
    game_state = getattr(game, "game_state", {}) or {}
    playcall = game_state.get("defense_playcall")
    # is_zone_defense is the discriminator used throughout phase_resolution/shot_manager
    # (it handles canonical ids, display names, and a no-DB legacy fallback).
    if is_zone_defense(playcall):
        # Match attack_drive_clearance: default to the 2-3 shell when the specific
        # variant can't be resolved (e.g. generic "Zone").
        variant = defense_zone_shell_variant(playcall) or "23"
        return _zone_read_map(off_lineup, def_lineup, variant)
    # Man (also the safe default when the playcall is unknown/None).
    defending_is_user = getattr(getattr(game, "defense_team", None), "is_user_team", False)
    return _man_read_map(off_lineup, def_lineup, game_state, defending_is_user)
