"""BIP pressure coordinates remain backend-owned and display-oriented."""

import random
from pathlib import Path

import pytest

from tests.test_oreb_kickout_coordinate_contract import _build_game


POSITIONS = ("PG", "SG", "SF", "PF", "C")
TURN_ANIMATION = (
    Path(__file__).parents[1]
    / "FrontEnd/static/js/phaser/animation/turnAnimation.js"
)
ANIMATION_DIR = TURN_ANIMATION.parent


def _pressure_destinations(*, pressure_type, away_offense, seed):
    game = _build_game(away_offense=away_offense)
    game.turns = []
    random.seed(seed)
    payload = game.turn_manager.setup_baseline_inbound(
        next_defensive_setup=pressure_type
    )
    return payload["dDestinations"]


def _baseline_payload(*, away_offense, seed):
    game = _build_game(away_offense=away_offense)
    game.turns = []
    random.seed(seed)
    return game.turn_manager.setup_baseline_inbound()


@pytest.mark.parametrize("pressure_type", ["FCP", "HCT"])
def test_bip_pressure_destinations_have_home_away_parity(pressure_type):
    home = _pressure_destinations(
        pressure_type=pressure_type,
        away_offense=False,
        seed=4815,
    )
    away = _pressure_destinations(
        pressure_type=pressure_type,
        away_offense=True,
        seed=4815,
    )

    assert home.keys() == away.keys() == set(POSITIONS)
    for position in POSITIONS:
        assert away[position]["x"] == pytest.approx(100.0 - home[position]["x"])
        assert away[position]["y"] == pytest.approx(home[position]["y"])


def test_baseline_inbound_ball_spot_has_home_away_parity():
    home = _baseline_payload(away_offense=False, seed=9371)
    away = _baseline_payload(away_offense=True, seed=9371)

    assert away["ball_spot"]["x"] == pytest.approx(100.0 - home["ball_spot"]["x"])
    assert away["ball_spot"]["y"] == pytest.approx(home["ball_spot"]["y"])


def test_frontend_inbound_setup_only_renders_backend_destinations():
    source = TURN_ANIMATION.read_text()
    start = source.index("async function runInboundSetup")
    inbound_setup = source[start : source.index("\n/**", start)]

    assert "BASELINE_INBOUND missing backend coordinates" in inbound_setup
    assert "const offenseTargets = turnData.oDestinations" in inbound_setup
    assert "const defenseTargets = turnData.dDestinations" in inbound_setup
    assert "const targetPos = defenseTargets[info.pos]" in inbound_setup
    assert "const pgDest = offenseTargets.PG" in inbound_setup
    assert "101 -" not in inbound_setup
    assert "Phaser.Math.Between" not in inbound_setup
    assert "HCO_STRING_SPOTS" not in inbound_setup
    assert "offense_setup_positions" not in inbound_setup


@pytest.mark.parametrize(
    "filename",
    [
        "turnoverAdapter.js",
        "fastBreak.js",
        "FreeThrowAnimationSystem.js",
        "animateGameTurns.js",
        "freeThrow.js",
        "ballManager.js",
    ],
)
def test_legacy_paths_do_not_call_baseline_inbound_setup(filename):
    source = (ANIMATION_DIR / filename).read_text()

    assert "await runInboundSetup({" not in source
    assert "await inboundSetup({" not in source
    assert "baseRunInboundSetup" not in source
