"""
Generate 100 distant-team training templates and insert them into gob-staging.distant_training.
Follows docs/docs_1_systems/06_GMO_Supporting_Systems/Distant_Team_Training_System.md.

Usage: python scripts/generate_distant_training_templates.py [--dry-run]
  --dry-run: build and print doc count, do not insert into DB.
"""
import os
import sys
import random
import argparse

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
os.chdir(_root)


def _load_env(filepath):
    out = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for path in [".env.local", ".env"]:
    for k, v in _load_env(path).items():
        os.environ.setdefault(k, v)

DB_NAME = "gob-staging"
COLLECTION = "distant_training"

# Team attribute keys (order matches engine). 12 total: shot_threshold, rebound_modifier, momentum_score + other 9.
TEAM_ATTR_KEYS = [
    "shot_threshold",
    "discipline",
    "fight",
    "rebound_modifier",
    "momentum_score",
    "offensive_efficiency",
    "team_chemistry",
    "defensive_efficiency",
    "fb_efficiency",
    "pt_efficiency",
    "fb_opp_modifier",
    "pt_opp_modifier",
]
TEAM_OTHER_9_KEYS = [
    "offensive_efficiency",
    "team_chemistry",
    "defensive_efficiency",
    "fb_efficiency",
    "pt_efficiency",
    "fb_opp_modifier",
    "pt_opp_modifier",
    "discipline",
    "fight",
]

PLAYER_ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT", "CH"]
NUM_PLAYERS = 12
NUM_PLAYER_ATTRS = len(PLAYER_ATTR_KEYS)
TOTAL_PLAYER_SLOTS = NUM_PLAYERS * NUM_PLAYER_ATTRS  # 156


def _build_enumeration_list(spec):
    """Build flat list from spec: list of (value, count)."""
    out = []
    for value, count in spec:
        out.extend([value] * count)
    return out


# --- TC (50 docs) enumerated values ---
TC_SHOT_THRESHOLD_SPEC = (
    [(-x, 3) for x in [5, 6, 7, 8, 9]]
    + [(-x, 4) for x in [10, 11, 12, 13, 14, 15]]
    + [(-x, 2) for x in [16, 17, 18]]
    + [(-x, 1) for x in [21, 22, 24, 28, 31]]
)
TC_REBOUND_SPEC = (
    [(0, 3)]
    + [(0.01, 7), (0.02, 7), (0.03, 7)]
    + [(0.04, 10), (0.05, 10)]
    + [(0.06, 2), (0.07, 2), (0.09, 2)]
)
TC_TEAM_OTHER9_SPEC = (
    [(11, 1), (14, 1), (15, 1)]
    + [(x, 8) for x in [16, 17, 18, 19, 20]]
    + [(21, 3), (22, 3)]
    + [(23, 1)]
)
TC_PLAYER_TOTAL_SPEC = (
    [(x, 1) for x in range(490, 495)]
    + [(x, 2) for x in range(495, 500)]
    + [(x, 6) for x in range(500, 505)]
    + [(x, 1) for x in range(505, 510)]
)

# --- Regular (50 docs) enumerated values ---
REG_SHOT_THRESHOLD_SPEC = (
    [(13, 2), (11, 2), (8, 2), (7, 2), (5, 2)]
    + [(-x, 5) for x in [5, 6, 7, 8, 9]]
    + [(-x, 2) for x in [10, 11, 12, 13, 14, 15]]
    + [(-x, 1) for x in [18, 22, 30]]
)
REG_REBOUND_SPEC = (
    [(-0.09, 3), (-0.06, 3), (-0.05, 3), (-0.02, 3), (-0.01, 3)]
    + [(0, 7), (0.01, 7), (0.02, 7), (0.03, 7)]
    + [(0.04, 2), (0.05, 2)]
    + [(0.06, 1), (0.07, 1), (0.09, 1)]
)
REG_TEAM_OTHER9_SPEC = (
    [(x, 2) for x in [9, 10, 11]]
    + [(x, 8) for x in [12, 13, 14, 15, 16]]
    + [(17, 2), (18, 2)]
)
REG_PLAYER_TOTAL_SPEC = (
    [(x, 1) for x in range(20, 35)]
    + [(x, 2) for x in range(35, 50)]
    + [(x, 1) for x in range(50, 55)]
)


def spread_team_other9_exact(total: int, is_tc: bool) -> dict:
    """Return 9 attribute deltas that sum exactly to total. TC: each in [0,3]. Regular: each in [-1,3]."""
    keys = TEAM_OTHER_9_KEYS
    if is_tc:
        lo, hi = 0, 3
        values = [0] * 9
        current = 0
        while current < total:
            i = random.randint(0, 8)
            if values[i] < hi:
                values[i] += 1
                current += 1
    else:
        lo, hi = -1, 3
        values = [-1] * 9
        current = -9
        to_add = total - current
        while to_add > 0:
            i = random.randint(0, 8)
            if values[i] < hi:
                values[i] += 1
                to_add -= 1
    return dict(zip(keys, values))


def fill_bucket(n: int, lo: int, hi: int, target_sum: int) -> list[int]:
    """Return n integers in [lo, hi] that sum to target_sum. Assumes target_sum is achievable."""
    if n <= 0:
        return []
    vals = [lo] * n
    current = n * lo
    while current < target_sum:
        i = random.randint(0, n - 1)
        if vals[i] < hi:
            vals[i] += 1
            current += 1
    return vals


def generate_tc_player_deltas(total: int) -> list[int]:
    """156 values summing to total. Buckets: 8-12 zeros, 0-3 in [10,12], 23-27 in [6,9], rest in [1,5]. Resample until valid."""
    max_attempts = 5000
    for _ in range(max_attempts):
        n0 = random.randint(8, 12)
        n_high = random.randint(0, 3)
        n_mid = random.randint(23, 27)
        n_rest = TOTAL_PLAYER_SLOTS - n0 - n_high - n_mid
        if n_rest < 0:
            continue
        sum_high_min = 10 * n_high
        sum_high_max = 12 * n_high
        sum_mid_min = 6 * n_mid
        sum_mid_max = 9 * n_mid
        sum_rest_min = 1 * n_rest
        sum_rest_max = 5 * n_rest
        total_min = sum_high_min + sum_mid_min + sum_rest_min
        total_max = sum_high_max + sum_mid_max + sum_rest_max
        if not (total_min <= total <= total_max):
            continue
        # Pick S_rest in [sum_rest_min, sum_rest_max] s.t. T - S_rest is in [sum_high_min+sum_mid_min, sum_high_max+sum_mid_max].
        rest_lo = max(sum_rest_min, total - sum_high_max - sum_mid_max)
        rest_hi = min(sum_rest_max, total - sum_high_min - sum_mid_min)
        if rest_lo > rest_hi:
            continue
        S_rest = random.randint(rest_lo, rest_hi)
        rem = total - S_rest
        mid_lo = max(sum_mid_min, rem - sum_high_max)
        mid_hi = min(sum_mid_max, rem - sum_high_min)
        if mid_lo > mid_hi:
            continue
        S_mid = random.randint(mid_lo, mid_hi)
        S_high = rem - S_mid
        assert sum_high_min <= S_high <= sum_high_max
        zeros = [0] * n0
        high_vals = fill_bucket(n_high, 10, 12, S_high) if n_high else []
        mid_vals = fill_bucket(n_mid, 6, 9, S_mid) if n_mid else []
        rest_vals = fill_bucket(n_rest, 1, 5, S_rest) if n_rest else []
        all_vals = zeros + high_vals + mid_vals + rest_vals
        random.shuffle(all_vals)
        assert len(all_vals) == TOTAL_PLAYER_SLOTS and sum(all_vals) == total
        return all_vals
    raise RuntimeError(f"Failed to generate TC player deltas for total={total} after {max_attempts} attempts")


def generate_regular_player_deltas(total: int) -> list[int]:
    """156 values in [-5,5] summing to total. At least 40% (63) in [-3,-1]. Max 1 of -5, 1 of 5, 3 of -4, 3 of 4."""
    # 63 slots in [-3,-1] (guarantees 40%), 8 slots for extremes (1*-5, 3*-4, 1*5, 3*4 → sum 0), 85 in [-3,3].
    # S1 = sum of 63 in [-3,-1] ∈ [-189, -63]. R = total - S1. 8 extremes sum to 0, so 85 must sum to R; R ∈ [-255,255].
    S1 = random.randint(-189, -63)
    low_63 = fill_bucket(63, -3, -1, S1)
    R = total - S1
    extremes = [-5, -4, -4, -4, 5, 4, 4, 4]  # sum 0, respects caps
    random.shuffle(extremes)
    mid_85 = fill_bucket(85, -3, 3, R)
    vals = low_63 + extremes + mid_85
    random.shuffle(vals)
    assert len(vals) == TOTAL_PLAYER_SLOTS and sum(vals) == total
    assert sum(1 for v in vals if -3 <= v <= -1) >= 63
    return vals


def deltas_to_players_dict(deltas: list[int]) -> dict:
    """Turn 156 flat deltas into {player_0: {SC: ..., SH: ...}, ...}."""
    assert len(deltas) == TOTAL_PLAYER_SLOTS
    players = {}
    for p in range(NUM_PLAYERS):
        start = p * NUM_PLAYER_ATTRS
        slice_ = deltas[start : start + NUM_PLAYER_ATTRS]
        players[f"player_{p}"] = dict(zip(PLAYER_ATTR_KEYS, slice_))
    return players


def build_team_values(
    shot_threshold: int,
    rebound_modifier: float,
    other9: dict,
) -> dict:
    """Build full team_values dict with all 12 keys (momentum_score always 0)."""
    out = {
        "shot_threshold": shot_threshold,
        "rebound_modifier": rebound_modifier,
        "momentum_score": 0,
    }
    for k in TEAM_OTHER_9_KEYS:
        out[k] = other9[k]
    return out


def build_docs() -> list[dict]:
    tc_shot = _build_enumeration_list(TC_SHOT_THRESHOLD_SPEC)
    tc_rebound = _build_enumeration_list(TC_REBOUND_SPEC)
    tc_team9 = _build_enumeration_list(TC_TEAM_OTHER9_SPEC)
    tc_player = _build_enumeration_list(TC_PLAYER_TOTAL_SPEC)
    reg_shot = _build_enumeration_list(REG_SHOT_THRESHOLD_SPEC)
    reg_rebound = _build_enumeration_list(REG_REBOUND_SPEC)
    reg_team9 = _build_enumeration_list(REG_TEAM_OTHER9_SPEC)
    reg_player = _build_enumeration_list(REG_PLAYER_TOTAL_SPEC)
    assert len(tc_shot) == 50 and len(reg_shot) == 50

    docs = []
    for i in range(50):
        other9 = spread_team_other9_exact(tc_team9[i], is_tc=True)
        team_values = build_team_values(tc_shot[i], tc_rebound[i], other9)
        player_deltas = generate_tc_player_deltas(tc_player[i])
        players = deltas_to_players_dict(player_deltas)
        docs.append({
            "training_type": "tc",
            "focus": "",
            "team_values": team_values,
            "players": players,
        })
    for i in range(50):
        other9 = spread_team_other9_exact(reg_team9[i], is_tc=False)
        team_values = build_team_values(reg_shot[i], reg_rebound[i], other9)
        player_deltas = generate_regular_player_deltas(reg_player[i])
        players = deltas_to_players_dict(player_deltas)
        docs.append({
            "training_type": "regular",
            "focus": "",
            "team_values": team_values,
            "players": players,
        })
    return docs


def main():
    parser = argparse.ArgumentParser(description="Generate distant training templates and insert into gob-staging")
    parser.add_argument("--dry-run", action="store_true", help="Build docs and print count only, do not insert")
    args = parser.parse_args()

    random.seed(42)
    docs = build_docs()
    print(f"Generated {len(docs)} documents ({sum(1 for d in docs if d['training_type'] == 'tc')} tc, {sum(1 for d in docs if d['training_type'] == 'regular')} regular).")

    if args.dry_run:
        print("Dry run: not inserting into DB.")
        return

    from BackEnd.db import client
    db = client[DB_NAME]
    coll = db[COLLECTION]
    coll.delete_many({})
    coll.insert_many(docs)
    print(f"Inserted {len(docs)} documents into {DB_NAME}.{COLLECTION}.")


if __name__ == "__main__":
    main()
