"""Stale-coords probe v2 (Q4/Q5). One (arm, seed) per process. Observation only unless POISON_Q4=1.

Q4  stored-coord DISPLACEMENT across an HCO turn, per player (offense/defense), man vs zone:
      S0 = player.coords when HCO turn N starts
      R  = player.coords when resolve_shot is entered in turn N          -> |R  - S0|
      S1 = player.coords when turn N+1 starts                             -> |S1 - S0|
    Hypothesis: sim never writes coords during HCO, so sim ~0 while played moves them.
    Played displacement is then the error sim's readers carry.
Q5  every call to a coord reader inside HCO turn N or turn N+1, re-evaluated with S0 in place
    of the live coords: does the nearest-player answer change? On played that is the number
    of outcomes a sim-stale position would flip (one turn of staleness only; it understates
    staleness carried across consecutive HCO turns).
POISON_Q4=1 disables every played coord writer on this path (apply_coords_from_animations_list,
    _uess_sync_emitted_shot_coords, sync_lineup_coords_from_turn): played displacement must
    collapse toward sim.
"""
import os, sys, json, math
os.environ.setdefault("OUT", "/dev/null")
REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
import scratch_equiv3_fbdedupe as W
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.game_manager import GameManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.utils import shared as SH
from BackEnd.engine import phase_resolution as PR

ZONES = {"2-3-zone", "3-2-zone", "1-3-1-zone"}
GM = [None]
_init = GameManager.__init__
def _gm_init(self, *a, **k):
    _init(self, *a, **k); GM[0] = self
GameManager.__init__ = _gm_init

ST = {"serial": 0, "ctx": None, "pending": None}
DISP, FLIPS = [], []

def _xy(p):
    c = getattr(p, "coords", None)
    if isinstance(c, dict) and c.get("x") is not None and c.get("y") is not None:
        return (float(c["x"]), float(c["y"]))
    return None

def _snap(gm):
    out = {}
    for side, team in (("off", gm.offense_team), ("def", gm.defense_team)):
        for p in (team.lineup or {}).values():
            if p is not None and getattr(p, "player_id", None) is not None:
                out[str(p.player_id)] = (side, _xy(p))
    return out

def _disp(stage, s0, s1, zone):
    for pid, (side, a) in s0.items():
        b = s1.get(pid)
        if a is None or b is None or b[1] is None:
            continue
        DISP.append((stage, side, zone, math.dist(a, b[1])))

_run = TurnManager.run_micro_turn
def run_micro_turn(self, *a, **k):
    gm = self.game
    ST["serial"] += 1
    pend, ST["pending"] = ST["pending"], None
    if pend is not None:
        _disp("next_turn", pend["s0"], _snap(gm), pend["zone"])
    ST["ctx"] = {"kind": "after_hco", "s0": pend["s0"], "zone": pend["zone"]} if pend else None
    return _run(self, *a, **k)
TurnManager.run_micro_turn = run_micro_turn

_hco = TurnManager.resolve_half_court_offense
def resolve_half_court_offense(self, *a, **k):
    gm = self.game
    zone = (gm.game_state or {}).get("defense_playcall") in ZONES
    s0 = _snap(gm)
    ST["ctx"] = {"kind": "hco", "s0": s0, "zone": zone}
    res = _hco(self, *a, **k)
    ST["pending"] = {"s0": s0, "zone": zone}
    return res
TurnManager.resolve_half_court_offense = resolve_half_court_offense

_rs = ShotManager.resolve_shot
def resolve_shot(self, *a, **k):
    ctx = ST["ctx"]
    if ctx and ctx["kind"] == "hco" and not ctx.get("resolved"):
        ctx["resolved"] = True
        _disp("pre_resolve", ctx["s0"], _snap(self.game), ctx["zone"])
    return _rs(self, *a, **k)
ShotManager.resolve_shot = resolve_shot

if os.environ.get("POISON_Q4") == "1":
    from BackEnd.models import game_manager as GMM
    from BackEnd.engine import rim_runner_fast_break as RRF
    for mod in (SH, PR, RRF):
        mod.apply_coords_from_animations_list = lambda *a, **k: None
    PR._uess_sync_emitted_shot_coords = lambda *a, **k: None
    SH.sync_lineup_coords_from_turn = lambda *a, **k: None
    GMM.sync_lineup_coords_from_turn = lambda *a, **k: None

def _stale_xy(p, s0):
    rec = s0.get(str(getattr(p, "player_id", None)))
    return rec[1] if rec and rec[1] is not None else _xy(p)

def _nearest(players, target, s0, penal=()):
    best_f = best_s = None; df = ds = float("inf")
    for p in players:
        if p is None:
            continue
        m = 1.2 if str(getattr(p, "player_id", None)) in penal else 1.0
        f = _xy(p); s = _stale_xy(p, s0)
        if f is not None and math.dist(f, target) * m < df:
            df, best_f = math.dist(f, target) * m, p
        if s is not None and math.dist(s, target) * m < ds:
            ds, best_s = math.dist(s, target) * m, p
    return best_f, df, best_s, ds

def _eval(fn, L):
    ctx = ST["ctx"]
    if not ctx:
        return
    s0 = ctx["s0"]
    try:
        if fn == "select_rebounder_by_score":
            bs = L.get("bounce_spot") or {}
            target = (float(bs["x"]), float(bs["y"]))
            players = [p for lu in (L.get("off_lineup"), L.get("def_lineup")) for p in (lu or {}).values()]
            penal = {str(x) for x in (L.get("penalize_player_ids") or ())}
            bf, _, bs_, _ = _nearest(players, target, s0, penal)
            off_ids = {str(getattr(p, "player_id", None)) for p in (L.get("off_lineup") or {}).values() if p}
            flip = bf is not bs_
            team_flip = (str(getattr(bf, "player_id", None)) in off_ids) != (str(getattr(bs_, "player_id", None)) in off_ids)
        elif fn == "over_the_back":
            reb = L.get("rebounder")
            rf, rs = _xy(reb), _stale_xy(reb, s0)
            if rf is None or rs is None:
                return
            opp = [p for p in (L.get("opposing_lineup") or {}).values() if p is not None]
            dfr = min((math.dist(rf, _xy(p)) for p in opp if _xy(p)), default=99)
            dst = min((math.dist(rs, _stale_xy(p, s0)) for p in opp if _stale_xy(p, s0)), default=99)
            flip = (dfr <= 4) != (dst <= 4)
            team_flip = flip
        elif fn == "putback_defender":
            sc = L.get("shooter_coords")
            reb = L.get("rebounder")
            target_f = (float(sc["x"]), float(sc["y"])) if sc else _xy(reb)
            target_s = target_f if sc else _stale_xy(reb, s0)
            defs = [p for p in (L.get("def_lineup") or {}).values() if p is not None]
            bf = min(defs, key=lambda p: math.dist(target_f, _xy(p) or (50, 25)), default=None)
            bs_ = min(defs, key=lambda p: math.dist(target_s, _stale_xy(p, s0) or (50, 25)), default=None)
            flip = bf is not bs_
            team_flip = False
        elif fn == "closest_to_victim":
            vc = L.get("victim_coords") or {}
            target = (float(vc["x"]), float(vc["y"]))
            given = L.get("defender_coords_by_pos") or {}
            defs = [p for pos, p in (L.get("def_lineup") or {}).items() if p is not None and pos not in given]
            bf, _, bs_, _ = _nearest(defs, target, s0)
            flip = bf is not bs_
            team_flip = False
        else:
            return
    except Exception:  # noqa: BLE001
        return
    FLIPS.append((fn, ctx["kind"], ctx["zone"], bool(flip), bool(team_flip)))

READERS = {
    SH.resolve_over_the_back_foul.__code__: "over_the_back",
    SH._resolve_oreb_putback_defender.__code__: "putback_defender",
    SH.select_rebounder_by_score.__code__: "select_rebounder_by_score",
    PR.select_defender_closest_to_victim.__code__: "closest_to_victim",
}
def _prof(frame, event, arg):
    if event == "call":
        name = READERS.get(frame.f_code)
        if name is not None:
            _eval(name, frame.f_locals)

if __name__ == "__main__":
    W._install_defense_census()
    sys.setprofile(_prof)
    rows = W.run_arm(W.ARM == "played")
    sys.setprofile(None)
    json.dump({"row": {k: v for k, v in rows[0].items() if k != "defense"}, "disp": DISP, "flips": FLIPS},
              open(os.environ["PROBE_OUT"], "w"))
    print(W.ARM, rows[0]["seed"], rows[0]["points_per_team"], len(DISP), len(FLIPS))
