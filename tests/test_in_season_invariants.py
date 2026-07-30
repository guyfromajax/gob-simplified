"""In-season model invariants, pinned as assertions so the next person to touch decay
or gain breaks a test instead of quietly eroding the league (this is the 3rd in-season
retune; RT held perfectly at 41/54/60 while attributes rotted underneath).

The invariant: a player trained at the coaching-quality REFERENCE allocation holds flat
per attribute; NEGLECT (base-0) declines; FOCUS (base-4/5) gains. And — because a
top-line metric (RT) masked the last defect and the offseason failed to restore what the
season eroded — the FULL CYCLE (season + rollover) must also hold, not just in-season."""
import logging
import random
import statistics
from collections import defaultdict

logging.disable(logging.CRITICAL)  # execute_training is chatty

from BackEnd.utils import player_development as dev
from BackEnd.models.training_execution_v2 import execute_training
from BackEnd.utils.position_ratings import compute_position_ratings

GROWTH = list(dev.GROWTH_ATTRS)
WEEKS = 26
POSITIONS = ("PG", "SG", "SF", "PF", "C")
FLAT_TOL = 3.0        # |net| below this = "holds flat" over a season
_YEARS = ("freshman", "sophomore", "junior", "senior")

# growth attribute → drill-slider path in the allocation dict
_DRILL = {
    "SC": ("offense", "inside"), "SH": ("offense", "outside"),
    "ID": ("defense", "inside"), "OD": ("defense", "outside"),
    "PS": ("technical", "passing"), "BH": ("technical", "ball_handling"),
    "RB": ("technical", "rebounding"), "ST": ("weight_room", "strength"),
    "AG": ("weight_room", "agility"),
    "ND": ("general", "conditioning"), "FT": ("general", "free_throws"),
    "IQ": ("general", "film_study"),
}


def _alloc(points: dict) -> dict:
    a = {"player_drills": {"offense": {"inside": 0, "outside": 0}, "defense": {"inside": 0, "outside": 0},
                           "technical": {"passing": 0, "ball_handling": 0, "rebounding": 0},
                           "weight_room": {"strength": 0, "agility": 0}},
         "general": {"conditioning": 0, "free_throws": 0, "film_study": 0, "breaks": 1},
         "team_drills": {}}
    for attr, p in points.items():
        grp, key = _DRILL.get(attr, (None, None))
        if grp is None:
            continue
        (a["general"] if grp == "general" else a["player_drills"][grp])[key] = p
    return a


def _players(n=40, height=78):
    out = []
    for i in range(n):
        attrs = {}
        for a in GROWTH + ["CH"]:
            attrs[f"anchor_{a}"] = 50
            attrs[a] = 50
        out.append({"_id": f"p{i}", "attributes": attrs, "year": _YEARS[i % 4], "height": height})
    return out


def _train_net(players, alloc, weeks=WEEKS, focus=None):
    before = {p["_id"]: {a: p["attributes"][f"anchor_{a}"] for a in GROWTH} for p in players}
    for _ in range(weeks):
        execute_training(players, {}, alloc, coaching_focus=focus)
    net = defaultdict(list)
    for p in players:
        for a in GROWTH:
            net[a].append(p["attributes"][f"anchor_{a}"] - before[p["_id"]][a])
    return {a: statistics.mean(v) for a, v in net.items()}


def test_reference_holds_flat_in_season():
    """INVARIANT 1: reference allocation → every ON-POSITION attribute nets ~0 over a season."""
    for pos in POSITIONS:
        random.seed(7)
        ref = dev.reference_allocation(pos)          # {top-3: 3.0, other on-position: 1.0}
        net = _train_net(_players(), _alloc({a: int(p) for a, p in ref.items()}))
        for attr in ref:                              # on-position attrs only
            assert abs(net[attr]) < FLAT_TOL, (
                f"{pos}/{attr}: in-season net {net[attr]:+.1f} not flat — the reference is rotting "
                f"(base-1 gain vs decay imbalance). |net| must be < {FLAT_TOL}.")


def test_reference_rt_below_rung_increment():
    """INVARIANT 2: reference RT net/season holds and stays below the smallest rung increment
    (so the offseason absorbs it and there is no claw-back)."""
    smallest_rung = 6  # FR->SO / JR->SR ladder step (mc_growth_fit: 35→41, 54→60)
    for pos in POSITIONS:
        random.seed(7)
        ref = dev.reference_allocation(pos)
        players = _players()
        rt0 = [compute_position_ratings({"attributes": p["attributes"], "height": p["height"]})[pos] for p in players]
        for _ in range(WEEKS):
            execute_training(players, {}, _alloc({a: int(p) for a, p in ref.items()}), coaching_focus=None)
        rt1 = [compute_position_ratings({"attributes": p["attributes"], "height": p["height"]})[pos] for p in players]
        rt_net = statistics.mean(b - a for a, b in zip(rt0, rt1))
        # holds (mildly-negative is fine — the offseason restores it) AND below the rung increment
        # (no claw-back). The upper bound is the real invariant.
        assert -3.0 < rt_net < smallest_rung, f"{pos}: reference RT net {rt_net:+.1f} outside (-3, {smallest_rung})"


def test_neglect_declines():
    """INVARIANT 3: a base-0 (neglected) attribute declines — deviation below the reference costs."""
    random.seed(7)
    pts = {a: 2 for a in GROWTH}
    pts["SC"] = 0                                     # neglect exactly one attribute
    net = _train_net(_players(), _alloc(pts))
    assert net["SC"] < -5, f"neglected base-0 SC net {net['SC']:+.1f} — neglect must cost (< -5)"


def test_reference_holds_flat_full_cycle():
    """INVARIANT 4: reference training + rollover (a FULL CYCLE) holds — no attribute erodes.
    Catches the class of defect where the season is flat but the OFFSEASON erodes (or vice
    versa): the last bug survived a full validation pass because the offseason failed to
    restore what the season eroded (SC -8.33 across the cycle) while RT held at 41/54/60."""
    for pos in POSITIONS:
        random.seed(11)
        ref = dev.reference_allocation(pos)
        ref_pts = {a: int(p) for a, p in ref.items()}
        eroded = []
        for i in range(24):
            pl = dev.init_career(pos, "Average", 40 + i, random.Random(100 + i))[0]
            base = {a: pl["attributes"].get(a, 0) for a in ref}          # on-position start values
            trainee = {"_id": "c", "attributes": dict(pl["attributes"]), "year": "freshman", "height": pl["height"]}
            for _ in range(WEEKS):
                execute_training([trainee], {}, _alloc(ref_pts), coaching_focus=None)
            fpd = {"player_id": "c", "meta": {"height": trainee["height"], "weight": pl["weight"], "year": "sophomore"},
                   "attributes": trainee["attributes"], "position_ratings": pl["position_ratings"],
                   "development": pl["development"], "entry_tier": "Average", "position_intent": pos}
            out = dev.develop_rollover(fpd, "sophomore", random.Random(200 + i), season_allocation=None)
            for a in ref:
                eroded.append((a, out["attributes"].get(a, 0) - base[a]))
        by_attr = defaultdict(list)
        for a, d in eroded:
            by_attr[a].append(d)
        for a, ds in by_attr.items():
            m = statistics.mean(ds)
            assert m > -FLAT_TOL, (
                f"{pos}/{a}: full-cycle net {m:+.1f} — the offseason did not restore what the season "
                f"eroded (must be > -{FLAT_TOL}).")
