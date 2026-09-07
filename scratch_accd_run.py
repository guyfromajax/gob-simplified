"""ACCEPTANCE D worker: make rate on the PREVIOUSLY-MISPLACED shot population.

A shot is "previously misplaced" if the shooter's authored pos_action carried the
spot name under "spot" only — the population the old dispatch sent to (50,25).
That classification is a property of the SKELETON, so it is computable identically
before and after the fix, which is what makes the two runs comparable.

ONE arm, ONE seed, ONE process, fresh in-memory DB (equiv-v3 discipline).
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ARM = os.environ.get("ARM", "played")
SEED = int(os.environ["SEED"])
OUT = os.environ["OUT"]

# Reuse the equiv-v3 worker's isolated construction and played-arm gating verbatim, so
# this probe measures the same two arms the distribution table came from.
import scratch_harness_run as HR
from BackEnd.utils import sim_random, training_random
import random as _stdlib
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter

import BackEnd.engine.defender_placement as DP
import BackEnd.models.animator as AN

CENTRE = (50.0, 25.0)

# build-order -> classification of the shooter's authored pos_action
CLASS_BY_BUILD = {}
BUILD_N = [0]
SHOOTER_COORD = {}
BY_TURN_IDX = {}
TALLY = Counter()


def _classify_shooter(skeleton):
    """(class, shooter_pos, step_idx) for the SHOOT pos_action in this skeleton.

    It is the shoot pos_action, not the shooter's last pos_action, that decides the
    coordinate the build places him on and therefore the coordinate the shot contest
    and the 2PT/3PT classifier read. Scanned backwards, matching
    set_shooter_coords_from_skeleton_last_step.
    """
    steps = skeleton.get("steps") or []
    for i in range(len(steps) - 1, -1, -1):
        for pos, pa in (steps[i].get("pos_actions") or {}).items():
            if not isinstance(pa, dict):
                continue
            if (pa.get("action") or "").lower().strip() != "shoot":
                continue
            if "coords" in pa:
                return "COORDS", pos, i
            if "location" in pa:
                return "LOCATION", pos, i
            if "spot" in pa:
                # THE previously-misplaced population: the old dispatch ignored this
                # key and placed him on the centre logo, which the contest then read.
                return "SPOT_ONLY", pos, i
            return "NONE", pos, i
    return None, None, None


def _install():
    orig = DP.build_all_animations

    def wrapped(game, skeleton, off_lineup, def_lineup, *a, **k):
        out = orig(game, skeleton, off_lineup, def_lineup, *a, **k)
        try:
            cls, pos, sidx = _classify_shooter(skeleton)
            if cls:
                # Stamp on the skeleton so the join survives into the turn record.
                skeleton["_accd_class"] = cls
                skeleton["_accd_shooter_pos"] = pos
                player = (off_lineup or {}).get(pos)
                pid = getattr(player, "player_id", None)
                rows = out[0] if isinstance(out, tuple) else out
                if pid is not None and isinstance(rows, list):
                    for anim in rows:
                        if not isinstance(anim, dict):
                            continue
                        if str(anim.get("playerId")) != str(pid):
                            continue
                        mv = anim.get("movement") or []
                        # The built coordinate at the SHOOT step is what the contest reads.
                        wp = mv[sidx] if sidx is not None and sidx < len(mv) else (mv[-1] if mv else None)
                        c = (wp or {}).get("coords") or {}
                        if c.get("x") is not None:
                            skeleton["_accd_shot_xy"] = [c.get("x"), c.get("y")]
                # ARM-INDEPENDENT JOIN. The skeleton stamp above does not survive into
                # the sim arm's turn records (its skeleton is a different object), so pair
                # by turn index instead: turns are appended as they complete, so the build
                # running while len(turns)==i belongs to turn i. Last build wins, which is
                # the one whose coords the contest actually read.
                tl = getattr(game, "turns", None)
                if isinstance(tl, list):
                    BY_TURN_IDX[len(tl)] = (cls, skeleton.get("_accd_shot_xy"))
                TALLY[f"classified:{cls}"] += 1
        except Exception as e:
            TALLY[f"probe-error:{type(e).__name__}:{e}"[:80] ] += 1
        return out

    DP.build_all_animations = wrapped
    if hasattr(AN, "build_all_animations"):
        AN.build_all_animations = wrapped


_install()

if ARM == "played":
    HR._install_played_arm()

sim_random.seed(SEED)
training_random.seed(SEED)
_stdlib.seed(SEED)
gm = GameManager("Lancaster", "Bentley-Truman")
_d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
      "hc_trap": 5, "fc_press": 5}
gm.home_team.strategy_settings = _d.copy()
gm.away_team.strategy_settings = _d.copy()
_err = None
for _q in range(4):
    try:
        simulate_quarter(gm, game_id="%024x" % (0xD0000 + SEED))
    except Exception as e:
        _err = f"{type(e).__name__}: {e}"
        break

# ---- join: per-turn outcome against the stamped classification -------------
BY_CLASS = defaultdict(Counter)
POINTS = defaultdict(int)
ON_LOGO = defaultdict(Counter)

STAMP_AGREE = Counter()
for _i, t in enumerate(gm.turns or []):
    sk = t.get("skeleton") or {}
    paired = BY_TURN_IDX.get(_i)
    cls = (paired[0] if paired else None) or sk.get("_accd_class")
    if not cls:
        continue
    if sk.get("_accd_class"):
        STAMP_AGREE["agree" if sk["_accd_class"] == cls else "disagree"] += 1
    rt = str(t.get("result_type") or "")
    if rt not in ("MAKE", "MISS", "BLOCK"):
        continue
    BY_CLASS[cls][rt] += 1
    BY_CLASS[cls]["shots"] += 1
    pts = t.get("points") or t.get("points_scored") or 0
    try:
        POINTS[cls] += int(pts)
    except Exception:
        pass
    if t.get("shot_classification") or t.get("is_three") is not None:
        BY_CLASS[cls][f"is3:{bool(t.get('is_three'))}"] += 1
    xy = (paired[1] if paired and paired[1] else sk.get("_accd_shot_xy")) or [None, None]
    if xy[0] is not None:
        on = abs(float(xy[0]) - CENTRE[0]) < 0.01 and abs(float(xy[1]) - CENTRE[1]) < 0.01
        ON_LOGO[cls]["logo" if on else "real"] += 1

json.dump({
    "arm": ARM, "seed": SEED,
    "tally": dict(TALLY),
    "by_class": {k: dict(v) for k, v in BY_CLASS.items()},
    "points": dict(POINTS),
    "on_logo": {k: dict(v) for k, v in ON_LOGO.items()},
    "turns": len(gm.turns or []), "error": _err, "stamp_agree": dict(STAMP_AGREE),
}, open(OUT, "w"))
