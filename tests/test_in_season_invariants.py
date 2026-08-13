"""In-season model invariants, pinned as assertions so the next person to touch decay
or gain breaks a test instead of quietly eroding the league (this is the 3rd in-season
retune; RT held perfectly at 41/54/60 while attributes rotted underneath).

The invariant: a player trained at the coaching-quality REFERENCE allocation keeps
primaries near flat; baseline (pts=1) may drag mildly now that 1–5 bands are distinct
(§10.6); NEGLECT (base-0) declines; FOCUS (base-4/5) gains. And — because a
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
FLAT_TOL = 4.0        # |net| below this = "holds flat" over a season (primaries mean)
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


def _players(n=40, height=78, position=None):
    out = []
    for i in range(n):
        attrs = {}
        for a in GROWTH + ["CH"]:
            attrs[f"anchor_{a}"] = 50
            attrs[a] = 50
        player = {"_id": f"p{i}", "attributes": attrs, "year": _YEARS[i % 4], "height": height}
        if position is not None:
            # Position-fit now scales gain, so position invariants must identify the
            # position they claim to measure instead of falling through to derived RT.
            player["position_intent"] = position
            player["training_position"] = position
        out.append(player)
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


def test_reference_primaries_hold_or_grow_in_season():
    """INVARIANT 1 (FREE-WILL): reference primaries (pts=3) hold or GROW in-season. Under the
    additive offseason, in-season no longer has to stay flat (it persists now), but primaries
    must not collapse or explode. Neglect is covered separately (INVARIANT 3)."""
    for pos in POSITIONS:
        random.seed(7)
        ref = dev.reference_allocation(pos)          # {top-3: 3.0, other on-position: 1.0}
        net = _train_net(_players(position=pos), _alloc({a: int(p) for a, p in ref.items()}))
        primaries = [a for a, p in ref.items() if int(p) >= 3]
        for attr in primaries:
            # Free-will primaries GROW and persist, so the bound is looser than the old flat
            # world — it only catches pathological runaway (a well-fit primary at pts=3 legitimately
            # gains ~10-14/season now).
            assert abs(net[attr]) < 20.0, (
                f"{pos}/{attr}: primary in-season net {net[attr]:+.1f} runaway (|net| must be < 20).")
        primary_mean = statistics.mean(net[a] for a in primaries)
        assert primary_mean > -FLAT_TOL, (
            f"{pos}: primary mean net {primary_mean:+.1f} collapsed — reference primaries "
            f"must hold or grow (> -{FLAT_TOL}).")


def _full_cycle(pos, n=24):
    """A reference-coached freshman: full season of training, then roll to sophomore.
    Returns (rt_nets, primary_attr_nets) across n players — the full-cycle deltas."""
    random.seed(11)
    ref = dev.reference_allocation(pos)
    ref_pts = {a: int(p) for a, p in ref.items()}
    primaries = [a for a, p in ref.items() if int(p) >= 3]
    rt_nets, prim_nets = [], []
    for i in range(n):
        pl = dev.init_career(pos, "Average", 40 + i, random.Random(100 + i))[0]
        rt0 = compute_position_ratings({"attributes": pl["attributes"], "height": pl["height"]})[pos]
        base = {a: pl["attributes"].get(a, 0) for a in primaries}
        tr = {"_id": "c", "attributes": dict(pl["attributes"]), "year": "freshman",
              "height": pl["height"], "position_intent": pos, "training_position": pos}
        for _ in range(WEEKS):
            execute_training([tr], {}, _alloc(ref_pts), coaching_focus=None)
        fpd = {"player_id": "c", "meta": {"height": tr["height"], "weight": pl["weight"], "year": "sophomore"},
               "attributes": tr["attributes"], "position_ratings": pl["position_ratings"],
               "development": pl["development"], "entry_tier": "Average", "position_intent": pos}
        out = dev.develop_rollover(fpd, "sophomore", random.Random(200 + i), season_allocation=None)
        rt1 = compute_position_ratings({"attributes": out["attributes"], "height": out["height"]})[pos]
        rt_nets.append(rt1 - rt0)
        prim_nets.append(statistics.mean(out["attributes"].get(a, 0) - base[a] for a in primaries))
    return rt_nets, prim_nets


def test_in_season_persists_through_offseason():
    """INVARIANT 2 (FREE-WILL): a reference-trained season PERSISTS through the offseason — the
    offseason ADDS a reduced increment on top and does NOT claw the in-season gain back (the
    defining free-will property, replacing the old 'in-season stays below the rung' claw-back
    invariant). Full-cycle RT nets positive league-wide; no position is significantly clawed back."""
    per_pos = {pos: statistics.mean(_full_cycle(pos)[0]) for pos in POSITIONS}
    for pos, m in per_pos.items():
        assert m > -3.0, f"{pos}: full-cycle RT net {m:+.1f} — offseason clawed back in-season (must be > -3)."
    league = statistics.mean(per_pos.values())
    assert league > 2.0, f"league full-cycle RT net {league:+.1f} — training must PERSIST and grow (> +2)."


def test_neglect_declines():
    """INVARIANT 3: a base-0 (neglected) attribute declines — deviation below the reference costs."""
    random.seed(7)
    pts = {a: 2 for a in GROWTH}
    pts["SC"] = 0                                     # neglect exactly one attribute
    net = _train_net(_players(), _alloc(pts))
    assert net["SC"] < -5, f"neglected base-0 SC net {net['SC']:+.1f} — neglect must cost (< -5)"


def test_full_cycle_grows():
    """INVARIANT 4 (FREE-WILL): reference training + rollover NET GROWS primaries across a full
    cycle — training persists and the offseason adds, so a season is no longer erased (the old
    invariant only asked that it 'not erode'; free-will asks that it GROW)."""
    per_pos = {pos: statistics.mean(_full_cycle(pos)[1]) for pos in POSITIONS}
    for pos, m in per_pos.items():
        assert m > -2.0, f"{pos}: full-cycle primary net {m:+.1f} eroded (must be > -2)."
    league = statistics.mean(per_pos.values())
    assert league > 2.0, f"league full-cycle primary net {league:+.1f} — primaries must grow (> +2)."
