#!/usr/bin/env python3
"""Dynamic HCO Set Plays — Stage D prototype / sanity harness.

Reproducible (seeded) Monte-Carlo over the two locked set-play mechanics, runnable with no DB or
server:

  1. Recovery roll (_setplay_recovery_roll) — re-enter-the-skeleton vs forced-freelance rate across
     a grid of offense (chem+off_eff) vs defense (chem+def_eff) strength. Validates the locked
     formula `(chem+eff) × d6` behaves monotonically (stronger offense → recovers more).
  2. Walk path distribution (_resolve_hco_offense_shot_dynamic, is_setplay=True) — over N possessions with a
     plausible random decision stream, tally how possessions terminate: per-step hot read, forced
     subtle → re-enter, forced subtle → freelance, or end-of-walk forced shot. Validates that the
     offense NEVER self-initiates a subtle (offense_reads is forced False) and that the
     recovery/freelance split fires only off defense pressure.

Run:  MONGO_URI="" MONGO_DB_NAME="gob-test" python3 dynamic_setplay_prototype.py
"""
import random
import BackEnd.engine.phase_resolution as PR
import BackEnd.engine.motion_step_decision as MSD

SEED = 1234
N = 4000


class _Player:
    def __init__(self, pid):
        self.player_id = pid
        self.attributes = {k: 50 for k in ("SC", "ST", "AG", "SH", "ID", "OD", "IQ", "CH")}


class _Team:
    def __init__(self, tid, chem=7, eff=0, aggression=2):
        self.team_id = tid
        self.is_user_team = False
        self.team_attributes = {"discipline": 0, "fight": 0, "offensive_efficiency": eff,
                                "defensive_efficiency": eff, "team_chemistry": chem}
        self.strategy_calls = {"aggression_call": "normal", "tempo_call": "normal"}
        self.strategy_settings = {"aggression": aggression}


class _Game:
    def __init__(self, off, deff, shot_clock=24):
        self.offense_team = off
        self.defense_team = deff
        self.home_team = off
        self.away_team = deff
        self.game_state = {"defense_playcall": "Man", "shot_clock_remaining": shot_clock}


def _step(loc, ts):
    return {"timestamp": ts, "pos_actions": {"PG": {"location": loc, "action": "handle_ball"}}, "events": []}


def _skel():
    # all-inside spots → end-of-walk / forced shots stay inside (no attack-drive geometry needed)
    return {"steps": [_step("basketSpot", i * 1000) for i in range(4)]}


def recovery_grid():
    print("── 1. Recovery roll: re-enter %% (rows=offense chem+eff, cols=defense chem+eff) ──")
    rng = random.Random(SEED)
    levels = [(5, 0), (7, 3), (10, 6)]
    hdr = "  off\\def |" + "".join(f"{c[0]+c[1]:>7}" for c in levels)
    print(hdr)
    for o in levels:
        off = _Team("O", chem=o[0], eff=o[1])
        row = f"{o[0]+o[1]:>9} |"
        for d in levels:
            g = _Game(off, _Team("D", chem=d[0], eff=d[1]))
            wins = sum(PR._setplay_recovery_roll(g, rng=rng) for _ in range(N)) / N
            row += f"{wins*100:>6.0f}%"
        print(row)


def walk_distribution():
    print("\n── 2. Walk path distribution over", N, "possessions (aggression=3) ──")
    rng = random.Random(SEED)
    # Terminal outcome of each possession + how many saw a defense-forced subtle. cur holds
    # per-possession flags the stubs write into; offense_subtle_seen must stay False forever.
    tally = {"hot_read_or_dish_shot": 0, "forced_freelance": 0, "end_of_walk_forced_shot": 0}
    subtle_forced = {"n": 0}
    offense_subtle_seen = {"hit": False}
    cur = {}

    orig = (MSD.should_shoot, MSD.decide_step_action, PR._hco_blocked_dish_targets,
            PR._hco_pass_lane_dist, PR._roll_subtle_defender_reads, PR._resolve_freelance)
    PR._hco_blocked_dish_targets = lambda *a, **k: set()
    PR._hco_pass_lane_dist = lambda *a, **k: 100.0
    PR._roll_subtle_defender_reads = lambda *a, **k: {}

    def fake_resolve_freelance(*a, **k):
        cur["freelance"] = True
        return {"skeleton": {"steps": []}, "shooter_pos": "PG", "shot_type": "inside", "_freelance": True}

    def fake_should_shoot(*a, **k):
        # ~12% per look the BH (or a teammate via dish) takes the hot read; tag it so the terminal
        # shot is attributed to a hot read rather than the end-of-walk fallback.
        if rng.random() < 0.12:
            cur["hot_read"] = True
            return {"shooter_pos": "PG", "shot_type": "inside", "via_pass": False, "hot_read": True}
        return None

    def fake_decide(*a, **k):
        # The offense NEVER reads in a set play — any non-ADVANCE here is defense-driven.
        if k.get("offense_reads") is not False:
            offense_subtle_seen["hit"] = True
        if not k.get("defense_pressure"):
            return {"action": MSD.ADVANCE}
        r = rng.random()
        if r < 0.25:
            cur["subtle"] = True
            return {"action": MSD.SUBTLE_MOVEMENT}     # defense forced a subtle
        if r < 0.32:
            return {"action": MSD.FREELANCE_FORCED}    # defense knocked straight to freelance
        return {"action": MSD.ADVANCE}

    PR._resolve_freelance = fake_resolve_freelance
    MSD.should_shoot, MSD.decide_step_action = fake_should_shoot, fake_decide
    try:
        for _ in range(N):
            cur.clear()
            g = _Game(_Team("O"), _Team("D", aggression=3), shot_clock=24)
            _resolve_setplay_dynamic_seeded(g, rng)
            if cur.get("subtle"):
                subtle_forced["n"] += 1
            if cur.get("freelance"):
                tally["forced_freelance"] += 1
            elif cur.get("hot_read"):
                tally["hot_read_or_dish_shot"] += 1
            else:
                tally["end_of_walk_forced_shot"] += 1
    finally:
        (MSD.should_shoot, MSD.decide_step_action, PR._hco_blocked_dish_targets,
         PR._hco_pass_lane_dist, PR._roll_subtle_defender_reads, PR._resolve_freelance) = orig

    total = sum(tally.values()) or 1
    for k, v in tally.items():
        print(f"  {k:<26} {v:>6} ({v/total*100:4.1f}%)")
    print(f"  possessions with a defense-forced subtle: {subtle_forced['n']} "
          f"({subtle_forced['n']/total*100:.1f}%)")
    print(f"  offense self-initiated a subtle: {offense_subtle_seen['hit']}  (must be False)")


def _resolve_setplay_dynamic_seeded(game, rng):
    # The resolver uses the global `random`; seed it per-call for reproducibility.
    random.seed(rng.random())
    # cleanup 2026-07-13: the `_resolve_setplay_offense_shot_dynamic` delegate was removed → call the
    # unified resolver with is_setplay=True.
    return _resolve_hco_offense_shot_dynamic(_skel(), game,
                                             {"PG": _Player("o_pg")}, {"PG": _Player("d_pg")},
                                             is_setplay=True)


# import after the helper defs so the name is bound at module load
from BackEnd.engine.phase_resolution import _resolve_hco_offense_shot_dynamic  # noqa: E402


if __name__ == "__main__":
    recovery_grid()
    walk_distribution()
