#!/usr/bin/env python3
"""
Write one JSON file per Rim Runner branch for Phase 1 payload documentation.

Prerequisites: project dependencies installed (pymongo / same env you use for pytest).

Usage (from repo root):
    python scripts/dump_rim_runner_turn_contract.py

Output: tests/fixtures/rim_runner_contract/*.json

These files are for humans + docs (contract table); they are not asserted in CI unless
you add tests that read them.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from unittest.mock import patch

# Repo root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from fastapi.encoders import jsonable_encoder
except ImportError:  # pragma: no cover - dev env without deps

    def jsonable_encoder(obj):  # type: ignore[no-redef]
        import json

        def _default(o):
            if hasattr(o, "player_id"):
                return {
                    "player_id": o.player_id,
                    "name": getattr(o, "name", None),
                }
            raise TypeError(f"Not JSON serializable: {type(o)}")

        return json.loads(json.dumps(obj, default=_default))

from BackEnd.constants import POSITION_LIST
from BackEnd.constants.fast_break_play_types import RIM_RUNNER
from BackEnd.engine import rim_runner_fast_break as rr_mod
from BackEnd.engine.rim_runner_fast_break import resolve_rim_runner_fast_break
from tests.test_utils import build_mock_game


OUT_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "tests",
    "fixtures",
    "rim_runner_contract",
)


def _make_rr_game(*, high_pg_iq: bool = False, aggression: int = 2):
    game = build_mock_game()
    game.offense_team = game.home_team
    game.defense_team = game.away_team

    rebounder = game.home_team.lineup["C"]
    rebounder.player_id = "home_c"
    rebounder.coords = {"x": 35, "y": 26}
    for pos, x in [("PG", 42), ("SG", 38), ("SF", 45), ("PF", 32)]:
        p = game.home_team.lineup[pos]
        p.player_id = f"home_{pos.lower()}"
        p.coords = {"x": x, "y": 26}
        if pos == "PG" and high_pg_iq:
            p.attributes["IQ"] = 85

    for pos in POSITION_LIST:
        p = game.away_team.lineup[pos]
        p.player_id = f"away_{pos.lower()}"
        p.coords = {"x": 55, "y": 22}

    # Strong interceptor (away PG) for steal / bat tiers when intercept rand is high
    d0 = game.away_team.lineup["PG"]
    for attr, val in (("OD", 55), ("AG", 55), ("IQ", 55)):
        d0.attributes[attr] = val

    game.game_state["last_rebounder"] = rebounder
    tid = str(game.home_team.team_id)
    game.game_state["rim_runner_by_team_id"] = {tid: game.home_team.lineup["SF"].player_id}

    def_pid = game.away_team.lineup["PG"].player_id
    game.turns = [
        {
            "result_type": "MISS",
            "offense_getback": [def_pid],
            "ball_bounce_x": 35,
        }
    ]

    game.home_team.strategy_settings["aggression"] = aggression
    return game


@contextmanager
def _anim_stub():
    with patch.object(rr_mod.Animator, "capture_fast_break_animation", return_value=[]):
        yield


def _write(name: str, payload: dict) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{name}.json")
    encoded = jsonable_encoder(payload)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(encoded, f, indent=2, sort_keys=False)
        f.write("\n")
    print(f"Wrote {path}")


# Shared RNG prefix: burst + other_player steps + calculate_outlet_pass_score d6 (see shared.py)
_RR_PREFIX = [1, 22, 33, 2, 2, 2, 2, 2, 2, 3]


def sample_outlet_denied():
    # Outlet math loses with low offense roll / high defense roll on the two outlet d6.
    game = _make_rr_game()
    seq = _RR_PREFIX + [1, 6]
    with patch.object(rr_mod.random, "randint", side_effect=seq), _anim_stub():
        r = resolve_rim_runner_fast_break(game, RIM_RUNNER)
    _write("01_outlet_denied", r)


def sample_hold_up():
    game = _make_rr_game()
    seq = _RR_PREFIX + [6, 1, 1, 6, 3]
    with patch.object(rr_mod.random, "randint", side_effect=seq), patch.object(
        rr_mod.random, "choice", side_effect=[False]
    ), _anim_stub():
        r = resolve_rim_runner_fast_break(game, RIM_RUNNER)
    _write("02_hold_up", r)


def sample_open_lane_shot():
    game = _make_rr_game(high_pg_iq=True)
    # Primary defender burst math uses away PG; reset from interceptor buff so lane open wins.
    for attr, val in (("OD", 3), ("AG", 4), ("IQ", 1)):
        game.away_team.lineup["PG"].attributes[attr] = val
    seq = _RR_PREFIX + [6, 1, 6, 1, 6]

    def fake_shot(roles):
        return {
            "result_type": "MISS",
            "text": "contract sample shot",
            "possession_flips": False,
            "offense_team_id": game.offense_team.team_id,
            "current_turn": "FAST_BREAK",
            "next_play_type": "HCO",
        }

    with patch.object(rr_mod.random, "randint", side_effect=seq), _anim_stub(), patch.object(
        game.shot_manager, "resolve_shot", side_effect=fake_shot
    ):
        r = resolve_rim_runner_fast_break(game, RIM_RUNNER)
    _write("03_open_lane_shot", r)


def sample_completion_shot():
    # Crowded lane: burst closed, aggressive + lucky pass attempt, intercept roll low -> shot.
    game = _make_rr_game(aggression=3)
    # Intercept d6 must keep score ≤ tier_mid (200); OD/AG/IQ 55 → ×3 stays under bat tier.
    seq = _RR_PREFIX + [6, 1, 1, 6, 3, 3]

    def fake_shot(roles):
        return {
            "result_type": "MAKE",
            "text": "contract sample make",
            "possession_flips": False,
            "offense_team_id": game.offense_team.team_id,
            "current_turn": "FAST_BREAK",
            "next_play_type": "BASELINE_INBOUND",
        }

    with patch.object(rr_mod.random, "randint", side_effect=seq), patch.object(
        rr_mod.random, "choice", side_effect=[True]
    ), _anim_stub(), patch.object(game.shot_manager, "resolve_shot", side_effect=fake_shot):
        r = resolve_rim_runner_fast_break(game, RIM_RUNNER)
    _write("04_completion_shot", r)


def sample_bat_oob():
    game = _make_rr_game(aggression=3)
    # Intercept d6 = 5 -> score 275 on OD/AG/IQ 55 (...*5 = 275): steal? 275>250 True -> steal actually
    # Use 50 base * 5 = 250: not steal, bat; need defender base * r in (201,250].
    for attr, val in (("OD", 50), ("AG", 50), ("IQ", 50)):
        game.away_team.lineup["PG"].attributes[attr] = val
    seq = _RR_PREFIX + [6, 1, 1, 6, 3, 5, 4]

    with patch.object(rr_mod.random, "randint", side_effect=seq), patch.object(
        rr_mod.random, "choice", side_effect=[True]
    ), _anim_stub():
        r = resolve_rim_runner_fast_break(game, RIM_RUNNER)
    _write("05_bat_oob", r)


def sample_intercept_steal():
    game = _make_rr_game(aggression=3)
    for attr, val in (("OD", 55), ("AG", 55), ("IQ", 55)):
        game.away_team.lineup["PG"].attributes[attr] = val
    seq = _RR_PREFIX + [6, 1, 1, 6, 3, 6]

    def fake_to(roles, g, turnover_type="DEAD BALL", from_resolution_system=False):
        return {
            "result_type": "STEAL",
            "ball_handler": roles["ball_handler"],
            "text": "Fast Break! Steal sample",
            "time_elapsed": 4,
            "possession_flips": True,
            "offense_team_id": g.offense_team.team_id,
            "current_turn": "HCO",
            "next_play_type": "HCO",
            "next_turn": "HCO",
            "stealer_id": getattr(roles.get("defender"), "player_id", None),
            "stealer_name": "Sample Stealer",
            "victim_id": getattr(roles["ball_handler"], "player_id", None),
            "victim_name": "Sample Victim",
        }

    with patch.object(rr_mod.random, "randint", side_effect=seq), patch.object(
        rr_mod.random, "choice", side_effect=[True]
    ), patch("BackEnd.engine.phase_resolution.resolve_turnover_logic", side_effect=fake_to), _anim_stub():
        r = resolve_rim_runner_fast_break(game, RIM_RUNNER)
    _write("06_intercept_steal", r)


def main():
    sample_outlet_denied()
    sample_hold_up()
    sample_open_lane_shot()
    sample_completion_shot()
    sample_bat_oob()
    sample_intercept_steal()
    print("Done. Open tests/fixtures/rim_runner_contract/ and copy fields into the Phase 1 table.")


if __name__ == "__main__":
    main()
